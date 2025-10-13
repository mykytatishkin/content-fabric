"""
Parallel Voice Processor
Splits audio into chunks and processes them in parallel for faster voice conversion
"""

import os
import tempfile
import concurrent.futures
from pathlib import Path
from typing import Optional, List, Dict, Callable, Tuple
import numpy as np
from pydub import AudioSegment
import logging

try:
    import librosa
    import soundfile as sf
except ImportError:
    raise ImportError("librosa and soundfile are required. Install with: pip install librosa soundfile")

from core.utils.logger import get_logger

logger = get_logger(__name__)


class ParallelVoiceProcessor:
    """
    Parallel voice processor with audio chunking and multi-threaded processing
    
    Pipeline:
    1. Split input audio into 5-minute chunks
    2. Process chunks in parallel (transcribe + voice change)
    3. Reassemble chunks into final output
    4. If background music exists, preserve it through the process
    """
    
    def __init__(
        self,
        chunk_duration_minutes: int = 5,
        max_workers: Optional[int] = None,
        temp_dir: Optional[str] = None
    ):
        """
        Initialize Parallel Voice Processor
        
        Args:
            chunk_duration_minutes: Duration of each chunk in minutes (default: 5)
            max_workers: Maximum number of parallel workers (default: CPU count)
            temp_dir: Temporary directory for intermediate files
        """
        self.chunk_duration_minutes = chunk_duration_minutes
        self.chunk_duration_seconds = chunk_duration_minutes * 60
        self.max_workers = max_workers or os.cpu_count()
        self.temp_dir = temp_dir or tempfile.mkdtemp(prefix='parallel_voice_')
        
        Path(self.temp_dir).mkdir(parents=True, exist_ok=True)
        
        logger.info("Parallel Voice Processor initialized:")
        logger.info(f"  Chunk duration: {chunk_duration_minutes} minutes")
        logger.info(f"  Max workers: {self.max_workers}")
        logger.info(f"  Temp dir: {self.temp_dir}")
    
    def split_audio(
        self,
        input_file: str,
        output_dir: Optional[str] = None
    ) -> List[Dict[str, any]]:
        """
        Split audio file into equal chunks
        
        Args:
            input_file: Path to input audio file
            output_dir: Directory to save chunks (default: temp_dir)
            
        Returns:
            List of chunk info dictionaries with keys: path, index, start_time, end_time
        """
        if output_dir is None:
            output_dir = os.path.join(self.temp_dir, 'chunks')
        
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Splitting audio: {input_file}")
        logger.info(f"  Chunk duration: {self.chunk_duration_minutes} minutes")
        
        # Load audio with librosa for better performance
        audio, sr = librosa.load(input_file, sr=None, mono=False)
        
        # Handle stereo/mono
        if len(audio.shape) == 1:
            channels = 1
            duration = len(audio) / sr
        else:
            channels = audio.shape[0]
            duration = audio.shape[1] / sr
        
        logger.info(f"  Audio info: {duration:.2f}s, {sr}Hz, {channels} channels")
        
        # Calculate number of chunks
        chunk_samples = int(self.chunk_duration_seconds * sr)
        total_samples = len(audio) if channels == 1 else audio.shape[1]
        num_chunks = int(np.ceil(total_samples / chunk_samples))
        
        logger.info(f"  Creating {num_chunks} chunks...")
        
        chunks = []
        
        for i in range(num_chunks):
            start_sample = i * chunk_samples
            end_sample = min((i + 1) * chunk_samples, total_samples)
            
            start_time = start_sample / sr
            end_time = end_sample / sr
            
            # Extract chunk
            if channels == 1:
                chunk_audio = audio[start_sample:end_sample]
            else:
                chunk_audio = audio[:, start_sample:end_sample]
            
            # Save chunk
            chunk_path = os.path.join(output_dir, f'chunk_{i:04d}.wav')
            sf.write(chunk_path, chunk_audio.T if channels > 1 else chunk_audio, sr)
            
            chunk_info = {
                'path': chunk_path,
                'index': i,
                'start_time': start_time,
                'end_time': end_time,
                'duration': end_time - start_time,
                'sample_rate': sr,
                'channels': channels
            }
            
            chunks.append(chunk_info)
            
            logger.info(f"  Chunk {i+1}/{num_chunks}: {start_time:.1f}s - {end_time:.1f}s")
        
        logger.info(f"✅ Split into {len(chunks)} chunks")
        
        return chunks
    
    def process_chunks_parallel(
        self,
        chunks: List[Dict[str, any]],
        processor_func: Callable[[str, str], Dict],
        output_dir: Optional[str] = None
    ) -> List[Dict[str, any]]:
        """
        Process chunks in parallel using multiple threads
        
        Args:
            chunks: List of chunk info dictionaries
            processor_func: Function to process each chunk (input_path, output_path) -> result_dict
            output_dir: Directory to save processed chunks
            
        Returns:
            List of processed chunk info dictionaries
        """
        if output_dir is None:
            output_dir = os.path.join(self.temp_dir, 'processed_chunks')
        
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Processing {len(chunks)} chunks in parallel with {self.max_workers} workers...")
        
        processed_chunks = []
        
        def process_chunk(chunk_info: Dict) -> Dict:
            """Process single chunk"""
            chunk_idx = chunk_info['index']
            input_path = chunk_info['path']
            output_path = os.path.join(output_dir, f'processed_chunk_{chunk_idx:04d}.wav')
            
            logger.info(f"  [Worker] Processing chunk {chunk_idx}...")
            
            try:
                # Call the processor function
                result = processor_func(input_path, output_path)
                
                # Update chunk info
                processed_info = {
                    **chunk_info,
                    'processed_path': output_path,
                    'status': 'success',
                    'result': result
                }
                
                logger.info(f"  [Worker] Chunk {chunk_idx} completed ✅")
                
                return processed_info
                
            except Exception as e:
                logger.error(f"  [Worker] Chunk {chunk_idx} failed: {str(e)}")
                
                return {
                    **chunk_info,
                    'processed_path': None,
                    'status': 'failed',
                    'error': str(e)
                }
        
        # Process chunks in parallel
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = [executor.submit(process_chunk, chunk) for chunk in chunks]
            
            # Wait for all to complete
            for future in concurrent.futures.as_completed(futures):
                try:
                    processed_chunk = future.result()
                    processed_chunks.append(processed_chunk)
                except Exception as e:
                    logger.error(f"  Worker error: {str(e)}")
        
        # Sort by index to maintain order
        processed_chunks.sort(key=lambda x: x['index'])
        
        # Check for failures
        failed = [c for c in processed_chunks if c['status'] == 'failed']
        successful = [c for c in processed_chunks if c['status'] == 'success']
        
        logger.info(f"✅ Parallel processing complete: {len(successful)} successful, {len(failed)} failed")
        
        if failed:
            logger.warning(f"⚠️  Failed chunks: {[c['index'] for c in failed]}")
        
        return processed_chunks
    
    def reassemble_chunks(
        self,
        processed_chunks: List[Dict[str, any]],
        output_file: str,
        crossfade_ms: int = 100
    ) -> str:
        """
        Reassemble processed chunks into final output file
        
        Args:
            processed_chunks: List of processed chunk info dictionaries
            output_file: Path to output file
            crossfade_ms: Crossfade duration between chunks in milliseconds
            
        Returns:
            Path to output file
        """
        logger.info(f"Reassembling {len(processed_chunks)} chunks into: {output_file}")
        logger.info(f"  Crossfade: {crossfade_ms}ms")
        
        # Filter successful chunks
        successful_chunks = [c for c in processed_chunks if c['status'] == 'success']
        
        if not successful_chunks:
            raise ValueError("No successful chunks to reassemble")
        
        # Load first chunk
        first_chunk = successful_chunks[0]
        combined = AudioSegment.from_file(first_chunk['processed_path'])
        
        logger.info(f"  Starting with chunk 0 ({len(combined)/1000:.1f}s)")
        
        # Append remaining chunks with crossfade
        for i, chunk_info in enumerate(successful_chunks[1:], start=1):
            chunk_audio = AudioSegment.from_file(chunk_info['processed_path'])
            
            if crossfade_ms > 0:
                # Crossfade between chunks
                combined = combined.append(chunk_audio, crossfade=crossfade_ms)
            else:
                # Simple concatenation
                combined = combined + chunk_audio
            
            logger.info(f"  Added chunk {i} ({len(chunk_audio)/1000:.1f}s) - total: {len(combined)/1000:.1f}s")
        
        # Export final file
        file_ext = os.path.splitext(output_file)[1][1:] or 'wav'
        combined.export(output_file, format=file_ext)
        
        logger.info(f"✅ Reassembled into: {output_file}")
        logger.info(f"  Final duration: {len(combined)/1000:.1f}s")
        
        return output_file
    
    def process_with_background(
        self,
        input_file: str,
        output_file: str,
        voice_processor_func: Callable[[str, str], Dict],
        background_separator_func: Optional[Callable] = None,
        vocals_gain: float = 0.0,
        background_gain: float = -3.0
    ) -> str:
        """
        Complete parallel processing pipeline with background preservation
        
        Pipeline:
        1. Separate vocals from background (if separator provided)
        2. Split vocals into chunks
        3. Process chunks in parallel
        4. Reassemble chunks
        5. Mix with original background
        
        Args:
            input_file: Input audio file
            output_file: Output audio file
            voice_processor_func: Function to process vocals (input, output) -> result
            background_separator_func: Function to separate vocals (input, temp_dir) -> (vocals, background)
            vocals_gain: Volume adjustment for vocals (dB)
            background_gain: Volume adjustment for background (dB)
            
        Returns:
            Path to output file
        """
        logger.info("=" * 70)
        logger.info("PARALLEL VOICE PROCESSING PIPELINE")
        logger.info("=" * 70)
        
        # Step 1: Separate vocals from background (optional)
        vocals_file = input_file
        background_file = None
        
        if background_separator_func:
            logger.info("Step 1: Separating vocals from background...")
            vocals_file, background_file = background_separator_func(
                input_file,
                os.path.join(self.temp_dir, 'separation')
            )
            logger.info(f"  Vocals: {vocals_file}")
            logger.info(f"  Background: {background_file}")
        else:
            logger.info("Step 1: Skipping background separation")
        
        # Step 2: Split vocals into chunks
        logger.info("Step 2: Splitting vocals into chunks...")
        chunks = self.split_audio(
            vocals_file,
            os.path.join(self.temp_dir, 'vocal_chunks')
        )
        
        # Step 3: Process chunks in parallel
        logger.info("Step 3: Processing chunks in parallel...")
        processed_chunks = self.process_chunks_parallel(
            chunks,
            voice_processor_func,
            os.path.join(self.temp_dir, 'processed_vocal_chunks')
        )
        
        # Step 4: Reassemble chunks
        logger.info("Step 4: Reassembling processed chunks...")
        
        if background_file:
            # Temporary file for reassembled vocals
            reassembled_vocals = os.path.join(self.temp_dir, 'reassembled_vocals.wav')
            self.reassemble_chunks(processed_chunks, reassembled_vocals)
            
            # Step 5: Mix with background
            logger.info("Step 5: Mixing with original background...")
            self._mix_audio(
                reassembled_vocals,
                background_file,
                output_file,
                vocals_gain,
                background_gain
            )
        else:
            # Direct reassembly to output
            self.reassemble_chunks(processed_chunks, output_file)
        
        logger.info("=" * 70)
        logger.info("✅ PARALLEL PROCESSING COMPLETE")
        logger.info("=" * 70)
        
        return output_file
    
    def _mix_audio(
        self,
        vocals_file: str,
        background_file: str,
        output_file: str,
        vocals_gain: float = 0.0,
        background_gain: float = -3.0
    ) -> str:
        """Mix vocals with background"""
        logger.info(f"  Mixing audio:")
        logger.info(f"    Vocals: {vocals_file} (gain: {vocals_gain} dB)")
        logger.info(f"    Background: {background_file} (gain: {background_gain} dB)")
        
        # Load audio files
        vocals = AudioSegment.from_file(vocals_file)
        background = AudioSegment.from_file(background_file)
        
        # Apply gain
        if vocals_gain != 0:
            vocals = vocals + vocals_gain
        
        if background_gain != 0:
            background = background + background_gain
        
        # Match lengths
        if len(vocals) > len(background):
            silence = AudioSegment.silent(duration=len(vocals) - len(background))
            background = background + silence
        elif len(background) > len(vocals):
            silence = AudioSegment.silent(duration=len(background) - len(vocals))
            vocals = vocals + silence
        
        # Mix
        mixed = background.overlay(vocals)
        
        # Export
        file_ext = os.path.splitext(output_file)[1][1:] or 'wav'
        mixed.export(output_file, format=file_ext)
        
        logger.info(f"  ✅ Mixed audio: {output_file}")
        
        return output_file
    
    def cleanup(self):
        """Clean up temporary files"""
        import shutil
        
        if os.path.exists(self.temp_dir):
            try:
                shutil.rmtree(self.temp_dir)
                logger.info(f"Cleaned up temp directory: {self.temp_dir}")
            except Exception as e:
                logger.warning(f"Failed to cleanup temp directory: {str(e)}")


def create_parallel_processor(
    chunk_duration_minutes: int = 5,
    max_workers: Optional[int] = None
) -> ParallelVoiceProcessor:
    """
    Convenience function to create a parallel processor
    
    Args:
        chunk_duration_minutes: Duration of each chunk in minutes
        max_workers: Maximum number of parallel workers
        
    Returns:
        ParallelVoiceProcessor instance
    """
    return ParallelVoiceProcessor(
        chunk_duration_minutes=chunk_duration_minutes,
        max_workers=max_workers
    )

