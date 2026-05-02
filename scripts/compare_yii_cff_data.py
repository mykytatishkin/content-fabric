"""Data integrity verification: compare Yii2 vs CFF row counts."""

import logging
from sqlalchemy import text
from shared.db.connection import get_engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def verify():
    engine = get_engine()
    queries = {
        "Channels": ("SELECT COUNT(*) FROM youtube_channels", "SELECT COUNT(*) FROM platform_channels"),
        "Tasks": ("SELECT COUNT(*) FROM tasks", "SELECT COUNT(*) FROM content_upload_queue_tasks"),
        "Streams": ("SELECT COUNT(*) FROM stream", "SELECT COUNT(*) FROM live_stream_configurations"),
        "Daily Stats": ("SELECT COUNT(*) FROM youtube_channel_daily", "SELECT COUNT(*) FROM channel_daily_statistics"),
    }
    
    with engine.connect() as conn:
        for name, (yii_q, cff_q) in queries.items():
            yii_count = conn.execute(text(yii_q)).scalar()
            cff_count = conn.execute(text(cff_q)).scalar()
            
            diff = cff_count - yii_count
            status = "OK" if diff >= 0 else "MISSING DATA"
            
            logger.info(f"{name}: Yii={yii_count}, CFF={cff_count}, Diff={diff} [{status}]")

if __name__ == "__main__":
    verify()
