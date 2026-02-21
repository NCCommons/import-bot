"""
Report generation from bot activity database.

This module provides functionality to generate summary reports and
statistics from the bot's SQLite database. Reports can be generated
programmatically or via command-line execution.

Report Contents:
    - Total upload and page counts
    - Per-language breakdown
    - Recent error listing (for debugging)

Example:
    >>> from src.reports import Reporter
    >>> from src.database import Database
    >>> db = Database("./data/nc_files.db")
    >>> reporter = Reporter(db)
    >>> report = reporter.generate_summary()
    >>> print(report['total'])
    {'total_uploads': 150, 'total_pages': 45}

Command Line:
    python -m src.reports ./data/nc_files.db ./reports/summary.json
"""

import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from .database import Database

logger = logging.getLogger(__name__)


class Reporter:
    """
    Generates reports from bot activity database.

    Provides methods to query the database and generate structured
    reports in JSON format. Reports include aggregate statistics,
    per-language breakdowns, and recent error listings.

    Attributes:
        db: Database instance to query for report data.

    Example:
        >>> db = Database("./data/bot.db")
        >>> reporter = Reporter(db)
        >>> report = reporter.generate_summary()
        >>> reporter.save_report("./reports/summary.json")
    """

    def __init__(self, database: Database) -> None:
        """
        Initialize reporter with database connection.

        Args:
            database: Database instance to query for report data.
        """
        self.db: Database = database

    def generate_summary(self) -> Dict[str, Any]:
        """
        Generate comprehensive summary report of bot activity.

        Queries the database for:
        - Overall statistics (total uploads, pages)
        - Per-language upload breakdown
        - Recent errors for debugging

        Returns:
            Dictionary containing:
            - 'total': {'total_uploads': int, 'total_pages': int}
            - 'by_language': [{'language': str, 'upload_count': int}, ...]
            - 'recent_errors': [{'filename': str, 'language': str,
                                 'error': str, 'uploaded_at': str}, ...]

        Example:
            >>> report = reporter.generate_summary()
            >>> print(f"Total uploads: {report['total']['total_uploads']}")
            >>> for lang in report['by_language']:
            ...     print(f"{lang['language']}: {lang['upload_count']} uploads")
        """
        logger.info("Generating summary report")

        with self.db._get_connection() as conn:
            # Overall statistics
            total_stats: Dict[str, int] = self.db.get_statistics()

            # Per-language statistics
            by_language: List[Dict[str, Any]] = [
                dict(row)
                for row in conn.execute(
                    """
                    SELECT
                        language,
                        COUNT(*) as upload_count
                    FROM uploads
                    WHERE status = 'success'
                    GROUP BY language
                    ORDER BY upload_count DESC
                    """
                ).fetchall()
            ]

            # Recent errors (limited to 10 most recent)
            recent_errors: List[Dict[str, Any]] = [
                dict(row)
                for row in conn.execute(
                    """
                    SELECT
                        filename,
                        language,
                        error,
                        uploaded_at
                    FROM uploads
                    WHERE status = 'failed'
                    ORDER BY uploaded_at DESC
                    LIMIT 10
                    """
                ).fetchall()
            ]

            # Build report structure
            report: Dict[str, Any] = {
                "total": dict(total_stats),
                "by_language": by_language,
                "recent_errors": recent_errors,
            }

            return report

    def save_report(self, output_path: str = "./reports/summary.json") -> None:
        """
        Generate and save summary report to JSON file.

        Creates the output directory if it doesn't exist and writes
        the report as formatted JSON with UTF-8 encoding.

        Args:
            output_path: Path where the JSON report will be saved.
                Parent directories are created automatically.
                Default: "./reports/summary.json"

        Example:
            >>> reporter.save_report("./output/report.json")
            >>> # Report saved to ./output/report.json

        Note:
            The file is written with ensure_ascii=False to properly
            encode international characters in page titles and errors.
        """
        # Generate report data
        report: Dict[str, Any] = self.generate_summary()

        # Ensure output directory exists
        output_file: Path = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        # Write JSON with proper formatting
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        logger.info(f"Report saved to {output_path}")


# Standalone script entry point
if __name__ == "__main__":
    # Allow running as standalone script for quick report generation
    db_path: str = sys.argv[1] if len(sys.argv) > 1 else "./data/nc_files.db"
    output: str = sys.argv[2] if len(sys.argv) > 2 else "./reports/summary.json"

    db: Database = Database(db_path)
    reporter: Reporter = Reporter(db)
    reporter.save_report(output)

    print(f"Report generated: {output}")
