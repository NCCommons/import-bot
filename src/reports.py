"""
Report generation from database.

This module provides functionality to generate summary reports and statistics
from the bot's database.
"""

import json
import logging
from pathlib import Path

from src.database import Database

logger = logging.getLogger(__name__)


class Reporter:
    """
    Generates reports from bot activity database.

    Provides methods to generate summary statistics and export to JSON.
    """

    def __init__(self, database: Database):
        """
        Initialize reporter.

        Args:
            database: Database instance to query
        """
        self.db = database

    def generate_summary(self) -> dict:
        """
        Generate summary report of bot activity.

        Returns:
            Dictionary containing summary statistics
        """
        logger.info("Generating summary report")

        with self.db._get_connection() as conn:
            # Overall statistics
            total_stats = self.db.get_statistics()

            # Per-language statistics
            by_language = conn.execute("""
                SELECT
                    language,
                    COUNT(*) as upload_count
                FROM uploads
                WHERE status = 'success'
                GROUP BY language
                ORDER BY upload_count DESC
            """).fetchall()

            # Recent errors
            recent_errors = conn.execute("""
                SELECT
                    filename,
                    language,
                    error,
                    uploaded_at
                FROM uploads
                WHERE status = 'failed'
                ORDER BY uploaded_at DESC
                LIMIT 10
            """).fetchall()

            # Build report
            report = {
                'total': dict(total_stats),
                'by_language': [dict(row) for row in by_language],
                'recent_errors': [dict(row) for row in recent_errors]
            }

            return report

    def save_report(self, output_path: str = './reports/summary.json'):
        """
        Generate and save summary report to JSON file.

        Args:
            output_path: Path to save the report
        """
        # Generate report
        report = self.generate_summary()

        # Ensure output directory exists
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        # Write to file
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        logger.info(f"Report saved to {output_path}")


# Standalone script functionality
if __name__ == '__main__':
    # Allow running as standalone script
    import sys

    db_path = sys.argv[1] if len(sys.argv) > 1 else './data/nc_files.db'
    output = sys.argv[2] if len(sys.argv) > 2 else './reports/summary.json'

    db = Database(db_path)
    reporter = Reporter(db)
    reporter.save_report(output)

    print(f"Report generated: {output}")
