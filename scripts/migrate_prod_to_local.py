#!/usr/bin/env python3
"""Migrate production database to local Docker MySQL (dev-test-env).

This script handles the full migration workflow:
1. Creates a backup dump from the production server via SSH
2. Starts local Docker containers if not running
3. Restores the dump to local Docker MySQL
4. Verifies the migration by checking record counts

Usage:
    python scripts/migrate_prod_to_local.py
    python scripts/migrate_prod_to_local.py --backup-only
    python scripts/migrate_prod_to_local.py --restore-only
    python scripts/migrate_prod_to_local.py --verify-only

Example:
    # Full migration
    $ python scripts/migrate_prod_to_local.py

    # Only backup (useful for scheduled backups)
    $ python scripts/migrate_prod_to_local.py --backup-only

    # Restore from existing dump
    $ python scripts/migrate_prod_to_local.py --restore-only
"""

import argparse
import logging
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

from dotenv import load_dotenv

# Configure logging with Google style format
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProductionConfig:
    """Configuration for production server connection.

    All values are loaded from environment variables.
    Set these in your .env file or export them before running.
    """
    host: str
    ssh_user: str
    database: str
    mysql_user: str
    mysql_password: str

    @classmethod
    def from_env(cls) -> 'ProductionConfig':
        """Create config from environment variables."""
        host = os.getenv('PROD_SSH_HOST')
        ssh_user = os.getenv('PROD_SSH_USER', 'root')
        database = os.getenv('PROD_MYSQL_DATABASE', 'content_fabric')
        mysql_user = os.getenv('PROD_MYSQL_USER')
        mysql_password = os.getenv('PROD_MYSQL_PASSWORD')

        missing = []
        if not host:
            missing.append('PROD_SSH_HOST')
        if not mysql_user:
            missing.append('PROD_MYSQL_USER')
        if not mysql_password:
            missing.append('PROD_MYSQL_PASSWORD')

        if missing:
            raise MigrationError(
                f"Missing required environment variables: {', '.join(missing)}\n"
                "Set them in .env.prod or export before running."
            )

        return cls(
            host=host,
            ssh_user=ssh_user,
            database=database,
            mysql_user=mysql_user,
            mysql_password=mysql_password
        )


@dataclass(frozen=True)
class LocalConfig:
    """Configuration for local Docker MySQL."""
    container_name: str = "dev-test-env-mysql"
    host: str = "localhost"
    port: int = 3306
    database: str = "content_fabric"
    user: str = "dev_user"
    password: str = "dev_pass"
    root_password: str = "dev_root_pass"


@dataclass(frozen=True)
class PathConfig:
    """Path configuration for the migration."""
    script_dir: Path
    project_root: Path
    docker_dir: Path
    init_dir: Path
    dump_file: Path

    @classmethod
    def create(cls) -> 'PathConfig':
        """Create PathConfig with computed paths."""
        script_dir = Path(__file__).parent.resolve()
        project_root = script_dir.parent
        docker_dir = project_root / "docker"
        init_dir = docker_dir / "init"
        dump_file = init_dir / "production_dump.sql"
        return cls(
            script_dir=script_dir,
            project_root=project_root,
            docker_dir=docker_dir,
            init_dir=init_dir,
            dump_file=dump_file
        )


class MigrationError(Exception):
    """Custom exception for migration errors."""
    pass


def run_command(
    command: str,
    capture_output: bool = False,
    check: bool = True,
    timeout: Optional[int] = None
) -> subprocess.CompletedProcess:
    """Execute a shell command with proper error handling.

    Args:
        command: Shell command to execute.
        capture_output: If True, capture stdout and stderr.
        check: If True, raise exception on non-zero exit code.
        timeout: Command timeout in seconds.

    Returns:
        CompletedProcess instance with command results.

    Raises:
        MigrationError: If command fails and check is True.
    """
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=capture_output,
            text=True,
            check=check,
            timeout=timeout
        )
        return result
    except subprocess.CalledProcessError as e:
        raise MigrationError(f"Command failed: {command}\nError: {e.stderr}")
    except subprocess.TimeoutExpired as e:
        raise MigrationError(f"Command timed out: {command}")


def ensure_directories(paths: PathConfig) -> None:
    """Create necessary directories for migration.

    Args:
        paths: Path configuration object.
    """
    paths.init_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Directory ready: %s", paths.init_dir)


def backup_production(
    prod_config: ProductionConfig,
    paths: PathConfig
) -> Tuple[bool, str]:
    """Create mysqldump from production server.

    Args:
        prod_config: Production server configuration.
        paths: Path configuration object.

    Returns:
        Tuple of (success: bool, message: str).
    """
    logger.info("Creating production database dump...")
    logger.info("  Server: %s", prod_config.host)
    logger.info("  Database: %s", prod_config.database)

    # Build mysqldump command with proper escaping
    mysqldump_cmd = (
        f"mysqldump -u {prod_config.mysql_user} "
        f"-p'{prod_config.mysql_password}' "
        f"--single-transaction --routines --triggers "
        f"--set-gtid-purged=OFF "
        f"{prod_config.database}"
    )

    ssh_cmd = (
        f'ssh {prod_config.ssh_user}@{prod_config.host} "{mysqldump_cmd}" '
        f'> "{paths.dump_file}"'
    )

    try:
        run_command(ssh_cmd, timeout=600)  # 10 minute timeout

        # Verify dump file
        if not paths.dump_file.exists():
            return False, "Dump file was not created"

        size_bytes = paths.dump_file.stat().st_size
        size_mb = size_bytes / (1024 * 1024)

        if size_bytes < 1000:
            return False, f"Dump file too small ({size_bytes} bytes), likely empty or error"

        logger.info("Dump saved: %s", paths.dump_file)
        logger.info("  Size: %.2f MB", size_mb)
        return True, f"Backup complete: {size_mb:.2f} MB"

    except MigrationError as e:
        return False, str(e)


def check_docker_container(local_config: LocalConfig, paths: PathConfig) -> bool:
    """Check if Docker MySQL container is running and healthy.

    Args:
        local_config: Local Docker configuration.
        paths: Path configuration object.

    Returns:
        True if container is healthy, False otherwise.
    """
    logger.info("Checking Docker container status...")

    check_cmd = (
        f'docker ps --filter "name={local_config.container_name}" '
        f'--format "{{{{.Status}}}}"'
    )

    try:
        result = run_command(check_cmd, capture_output=True, check=False)
        status = result.stdout.strip().lower()

        if "healthy" in status:
            logger.info("Container %s is healthy", local_config.container_name)
            return True

        if "up" in status:
            logger.info("Container is up, waiting for healthy status...")
            return _wait_for_healthy(local_config)

        # Container not running, start it
        logger.warning("Container not running, starting Docker services...")
        return _start_docker_services(local_config, paths)

    except MigrationError:
        return False


def _wait_for_healthy(
    local_config: LocalConfig,
    max_attempts: int = 30,
    interval: int = 2
) -> bool:
    """Wait for container to become healthy.

    Args:
        local_config: Local Docker configuration.
        max_attempts: Maximum number of check attempts.
        interval: Seconds between attempts.

    Returns:
        True if container becomes healthy, False otherwise.
    """
    check_cmd = (
        f'docker ps --filter "name={local_config.container_name}" '
        f'--format "{{{{.Status}}}}"'
    )

    for attempt in range(max_attempts):
        time.sleep(interval)
        result = run_command(check_cmd, capture_output=True, check=False)

        if "healthy" in result.stdout.lower():
            logger.info("Container is now healthy")
            return True

        logger.info("  Waiting for healthy status... (%d/%d)", attempt + 1, max_attempts)

    logger.error("Container failed to become healthy after %d attempts", max_attempts)
    return False


def _start_docker_services(local_config: LocalConfig, paths: PathConfig) -> bool:
    """Start Docker Compose services.

    Args:
        local_config: Local Docker configuration.
        paths: Path configuration object.

    Returns:
        True if services started successfully, False otherwise.
    """
    try:
        start_cmd = f'cd "{paths.docker_dir}" && docker-compose up -d'
        run_command(start_cmd)
        return _wait_for_healthy(local_config)
    except MigrationError as e:
        logger.error("Failed to start Docker services: %s", e)
        return False


def restore_to_local(
    local_config: LocalConfig,
    paths: PathConfig
) -> Tuple[bool, str]:
    """Restore dump file to local Docker MySQL.

    Args:
        local_config: Local Docker configuration.
        paths: Path configuration object.

    Returns:
        Tuple of (success: bool, message: str).
    """
    logger.info("Restoring to local Docker MySQL...")

    if not paths.dump_file.exists():
        return False, f"Dump file not found: {paths.dump_file}"

    try:
        # Drop and recreate database for clean state
        logger.info("  Resetting database...")
        reset_cmd = (
            f'docker exec {local_config.container_name} mysql '
            f'-u root -p{local_config.root_password} '
            f'-e "DROP DATABASE IF EXISTS {local_config.database}; '
            f'CREATE DATABASE {local_config.database} '
            f'CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"'
        )
        run_command(reset_cmd, check=False)

        # Import dump (use root to avoid privilege issues with DEFINER)
        logger.info("  Importing dump file (this may take a while)...")
        import_cmd = (
            f'docker exec -i {local_config.container_name} mysql '
            f'-u root -p{local_config.root_password} '
            f'{local_config.database} < "{paths.dump_file}"'
        )
        run_command(import_cmd, timeout=600)

        logger.info("Database restored successfully")
        return True, "Restore complete"

    except MigrationError as e:
        return False, str(e)


def verify_migration(local_config: LocalConfig) -> dict:
    """Verify migration by counting records in key tables.

    Args:
        local_config: Local Docker configuration.

    Returns:
        Dictionary with table names and record counts.
    """
    logger.info("Verifying migration...")

    tables = [
        "youtube_channels",
        "google_consoles",
        "tasks",
        "youtube_account_credentials",
        "youtube_reauth_audit",
    ]

    results = {}
    for table in tables:
        query = f"SELECT COUNT(*) FROM {table}"
        cmd = (
            f'docker exec {local_config.container_name} mysql '
            f'-u {local_config.user} -p{local_config.password} '
            f'{local_config.database} -N -e "{query}"'
        )

        try:
            result = run_command(cmd, capture_output=True, check=False)
            count = result.stdout.strip()
            results[table] = int(count) if count.isdigit() else 0
            logger.info("  %s: %s records", table, count)
        except (MigrationError, ValueError):
            results[table] = -1
            logger.warning("  %s: failed to query", table)

    return results


def print_connection_info(local_config: LocalConfig) -> None:
    """Print connection information for the application.

    Args:
        local_config: Local Docker configuration.
    """
    separator = "=" * 60
    print(f"\n{separator}")
    print("MIGRATION COMPLETE!")
    print(separator)
    print("\nLocal Development Connection Info:")
    print("-" * 40)
    print(f"  Host:     {local_config.host}")
    print(f"  Port:     {local_config.port}")
    print(f"  Database: {local_config.database}")
    print(f"  User:     {local_config.user}")
    print(f"  Password: {local_config.password}")
    print("-" * 40)
    print("\nUpdate your .env file with:")
    print("-" * 40)
    print("  DB_TYPE=mysql")
    print(f"  MYSQL_HOST={local_config.host}")
    print(f"  MYSQL_PORT={local_config.port}")
    print(f"  MYSQL_DATABASE={local_config.database}")
    print(f"  MYSQL_USER={local_config.user}")
    print(f"  MYSQL_PASSWORD={local_config.password}")
    print("-" * 40)
    print("\nphpMyAdmin: http://localhost:8080")
    print(f"  Login: {local_config.user} / {local_config.password}")
    print(separator)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments.

    Returns:
        Parsed arguments namespace.
    """
    parser = argparse.ArgumentParser(
        description="Migrate production database to local Docker MySQL",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        "--backup-only",
        action="store_true",
        help="Only create backup, don't restore"
    )
    parser.add_argument(
        "--restore-only",
        action="store_true",
        help="Only restore from existing dump"
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Only verify existing migration"
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    return parser.parse_args()


def main() -> int:
    """Main entry point for the migration script.

    Returns:
        Exit code (0 for success, 1 for failure).
    """
    args = parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Load environment variables from .env.prod file
    script_dir = Path(__file__).parent.resolve()
    project_root = script_dir.parent
    env_prod_file = project_root / ".env.prod"

    if env_prod_file.exists():
        load_dotenv(env_prod_file)
    else:
        load_dotenv()  # Try default .env

    # Initialize configurations
    local_config = LocalConfig()
    paths = PathConfig.create()

    # Print header
    print("=" * 60)
    print("Content Fabric - Production to Local Migration")
    print(f"  Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    try:
        ensure_directories(paths)

        # Handle verify-only mode
        if args.verify_only:
            if not check_docker_container(local_config, paths):
                logger.error("Docker container not available")
                return 1
            verify_migration(local_config)
            return 0

        # Handle restore-only mode (no need for prod config)
        if args.restore_only:
            if not check_docker_container(local_config, paths):
                logger.error("Failed to start Docker container")
                return 1
            success, message = restore_to_local(local_config, paths)
            if not success:
                logger.error("Restore failed: %s", message)
                return 1
            verify_migration(local_config)
            print_connection_info(local_config)
            return 0

        # For backup operations, we need prod config
        prod_config = ProductionConfig.from_env()

        # Backup phase
        success, message = backup_production(prod_config, paths)
        if not success:
            logger.error("Backup failed: %s", message)
            return 1

        if args.backup_only:
            logger.info("Backup complete. Use --restore-only to restore later.")
            return 0

        # Docker check phase
        if not check_docker_container(local_config, paths):
            logger.error("Failed to start Docker container")
            return 1

        # Restore phase
        success, message = restore_to_local(local_config, paths)
        if not success:
            logger.error("Restore failed: %s", message)
            return 1

        # Verify phase
        verify_migration(local_config)

        # Print success info
        print_connection_info(local_config)

        return 0

    except KeyboardInterrupt:
        logger.warning("Migration interrupted by user")
        return 1
    except Exception as e:
        logger.exception("Unexpected error during migration: %s", e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
