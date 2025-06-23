"""
Export service for Reddit automation dashboard
Provides data export functionality in various formats (CSV, JSON, PDF)
"""
import csv
import json
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
from io import StringIO, BytesIO
import tempfile
import os

from analytics_engine import analytics_engine
from database import SessionLocal
from models import RedditAccount

logger = logging.getLogger(__name__)

class ExportService:
    """Service for exporting analytics data in various formats"""
    
    def __init__(self):
        self.supported_formats = ['json', 'csv', 'pdf']
    
    def export_account_analytics(self, account_id: int, format: str = 'json', days: int = 30) -> Dict[str, Any]:
        """Export comprehensive analytics for an account"""
        try:
            if format not in self.supported_formats:
                raise ValueError(f"Unsupported format: {format}")
            
            # Gather all analytics data
            karma_metrics = analytics_engine.get_karma_growth_analytics(account_id, days)
            engagement_metrics = analytics_engine.get_engagement_analytics(account_id, days)
            performance_metrics = analytics_engine.get_performance_analytics(account_id, days)
            subreddit_analytics = analytics_engine.get_subreddit_analytics(account_id, days)
            
            # Get account info
            db = SessionLocal()
            account = db.query(RedditAccount).filter(RedditAccount.id == account_id).first()
            db.close()
            
            if not account:
                raise ValueError(f"Account {account_id} not found")
            
            # Prepare export data
            export_data = {
                'export_info': {
                    'account_id': account_id,
                    'username': account.reddit_username,
                    'export_date': datetime.utcnow().isoformat(),
                    'period_days': days,
                    'format': format
                },
                'karma_analytics': {
                    'total_karma': karma_metrics.total_karma,
                    'post_karma': karma_metrics.post_karma,
                    'comment_karma': karma_metrics.comment_karma,
                    'growth_rate_daily': karma_metrics.growth_rate_daily,
                    'growth_rate_weekly': karma_metrics.growth_rate_weekly,
                    'growth_rate_monthly': karma_metrics.growth_rate_monthly,
                    'peak_growth_day': karma_metrics.peak_growth_day,
                    'trend_direction': karma_metrics.trend_direction
                },
                'engagement_analytics': {
                    'total_actions': engagement_metrics.total_actions,
                    'successful_actions': engagement_metrics.successful_actions,
                    'failed_actions': engagement_metrics.failed_actions,
                    'success_rate': engagement_metrics.success_rate,
                    'daily_average': engagement_metrics.daily_average,
                    'actions_by_type': engagement_metrics.actions_by_type,
                    'actions_by_subreddit': engagement_metrics.actions_by_subreddit,
                    'hourly_distribution': engagement_metrics.hourly_distribution
                },
                'performance_analytics': {
                    'automation_efficiency': performance_metrics.automation_efficiency,
                    'average_response_time': performance_metrics.average_response_time,
                    'error_rate': performance_metrics.error_rate,
                    'uptime_percentage': performance_metrics.uptime_percentage,
                    'most_active_hours': performance_metrics.most_active_hours,
                    'best_performing_subreddits': performance_metrics.best_performing_subreddits
                },
                'subreddit_analytics': subreddit_analytics
            }
            
            # Export in requested format
            if format == 'json':
                return self._export_json(export_data, account.reddit_username, days)
            elif format == 'csv':
                return self._export_csv(export_data, account.reddit_username, days)
            elif format == 'pdf':
                return self._export_pdf(export_data, account.reddit_username, days)
            
        except Exception as e:
            logger.error(f"Error exporting account analytics: {e}")
            raise
    
    def _export_json(self, data: Dict[str, Any], username: str, days: int) -> Dict[str, Any]:
        """Export data as JSON"""
        try:
            json_content = json.dumps(data, indent=2, default=str)
            filename = f"reddit_analytics_{username}_{days}days_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
            
            return {
                'format': 'json',
                'filename': filename,
                'content': json_content,
                'content_type': 'application/json',
                'size': len(json_content.encode('utf-8'))
            }
            
        except Exception as e:
            logger.error(f"Error exporting JSON: {e}")
            raise
    
    def _export_csv(self, data: Dict[str, Any], username: str, days: int) -> Dict[str, Any]:
        """Export data as CSV"""
        try:
            output = StringIO()
            
            # Write summary information
            output.write("Reddit Analytics Export\n")
            output.write(f"Account: {data['export_info']['username']}\n")
            output.write(f"Period: {data['export_info']['period_days']} days\n")
            output.write(f"Export Date: {data['export_info']['export_date']}\n")
            output.write("\n")
            
            # Karma Analytics
            output.write("KARMA ANALYTICS\n")
            karma_writer = csv.writer(output)
            karma_writer.writerow(['Metric', 'Value'])
            karma_data = data['karma_analytics']
            for key, value in karma_data.items():
                karma_writer.writerow([key.replace('_', ' ').title(), value])
            output.write("\n")
            
            # Engagement Analytics
            output.write("ENGAGEMENT ANALYTICS\n")
            engagement_writer = csv.writer(output)
            engagement_writer.writerow(['Metric', 'Value'])
            engagement_data = data['engagement_analytics']
            for key, value in engagement_data.items():
                if isinstance(value, dict):
                    for sub_key, sub_value in value.items():
                        engagement_writer.writerow([f"{key} - {sub_key}", sub_value])
                else:
                    engagement_writer.writerow([key.replace('_', ' ').title(), value])
            output.write("\n")
            
            # Actions by Type
            if 'actions_by_type' in engagement_data:
                output.write("ACTIONS BY TYPE\n")
                action_writer = csv.writer(output)
                action_writer.writerow(['Action Type', 'Count'])
                for action_type, count in engagement_data['actions_by_type'].items():
                    action_writer.writerow([action_type, count])
                output.write("\n")
            
            # Actions by Subreddit
            if 'actions_by_subreddit' in engagement_data:
                output.write("ACTIONS BY SUBREDDIT\n")
                subreddit_writer = csv.writer(output)
                subreddit_writer.writerow(['Subreddit', 'Count'])
                for subreddit, count in engagement_data['actions_by_subreddit'].items():
                    subreddit_writer.writerow([subreddit, count])
                output.write("\n")
            
            # Performance Analytics
            output.write("PERFORMANCE ANALYTICS\n")
            performance_writer = csv.writer(output)
            performance_writer.writerow(['Metric', 'Value'])
            performance_data = data['performance_analytics']
            for key, value in performance_data.items():
                if isinstance(value, list):
                    performance_writer.writerow([key.replace('_', ' ').title(), ', '.join(map(str, value))])
                else:
                    performance_writer.writerow([key.replace('_', ' ').title(), value])
            
            csv_content = output.getvalue()
            output.close()
            
            filename = f"reddit_analytics_{username}_{days}days_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
            
            return {
                'format': 'csv',
                'filename': filename,
                'content': csv_content,
                'content_type': 'text/csv',
                'size': len(csv_content.encode('utf-8'))
            }
            
        except Exception as e:
            logger.error(f"Error exporting CSV: {e}")
            raise
    
    def _export_pdf(self, data: Dict[str, Any], username: str, days: int) -> Dict[str, Any]:
        """Export data as PDF report"""
        try:
            # For PDF generation, we'll create a simple text-based report
            # In a production environment, you'd use libraries like reportlab or weasyprint
            
            report_content = self._generate_text_report(data)
            filename = f"reddit_analytics_{username}_{days}days_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.txt"
            
            return {
                'format': 'pdf',  # Note: This is actually text format for demo
                'filename': filename,
                'content': report_content,
                'content_type': 'text/plain',
                'size': len(report_content.encode('utf-8')),
                'note': 'PDF generation requires additional libraries. This is a text report.'
            }
            
        except Exception as e:
            logger.error(f"Error exporting PDF: {e}")
            raise
    
    def _generate_text_report(self, data: Dict[str, Any]) -> str:
        """Generate a formatted text report"""
        report = []
        
        # Header
        report.append("=" * 60)
        report.append("REDDIT AUTOMATION ANALYTICS REPORT")
        report.append("=" * 60)
        report.append("")
        
        # Export Info
        export_info = data['export_info']
        report.append(f"Account: {export_info['username']}")
        report.append(f"Account ID: {export_info['account_id']}")
        report.append(f"Analysis Period: {export_info['period_days']} days")
        report.append(f"Export Date: {export_info['export_date']}")
        report.append("")
        
        # Karma Analytics
        report.append("KARMA ANALYTICS")
        report.append("-" * 20)
        karma_data = data['karma_analytics']
        report.append(f"Total Karma: {karma_data['total_karma']:,}")
        report.append(f"Post Karma: {karma_data['post_karma']:,}")
        report.append(f"Comment Karma: {karma_data['comment_karma']:,}")
        report.append(f"Daily Growth Rate: {karma_data['growth_rate_daily']:.2f}")
        report.append(f"Weekly Growth Rate: {karma_data['growth_rate_weekly']:.2f}")
        report.append(f"Monthly Growth Rate: {karma_data['growth_rate_monthly']:.2f}")
        report.append(f"Trend Direction: {karma_data['trend_direction']}")
        if karma_data['peak_growth_day']:
            report.append(f"Peak Growth Day: {karma_data['peak_growth_day']}")
        report.append("")
        
        # Engagement Analytics
        report.append("ENGAGEMENT ANALYTICS")
        report.append("-" * 20)
        engagement_data = data['engagement_analytics']
        report.append(f"Total Actions: {engagement_data['total_actions']:,}")
        report.append(f"Successful Actions: {engagement_data['successful_actions']:,}")
        report.append(f"Failed Actions: {engagement_data['failed_actions']:,}")
        report.append(f"Success Rate: {engagement_data['success_rate']:.1%}")
        report.append(f"Daily Average: {engagement_data['daily_average']:.1f}")
        report.append("")
        
        # Actions by Type
        if engagement_data['actions_by_type']:
            report.append("Actions by Type:")
            for action_type, count in engagement_data['actions_by_type'].items():
                report.append(f"  {action_type}: {count:,}")
            report.append("")
        
        # Performance Analytics
        report.append("PERFORMANCE ANALYTICS")
        report.append("-" * 20)
        performance_data = data['performance_analytics']
        report.append(f"Automation Efficiency: {performance_data['automation_efficiency']:.1%}")
        report.append(f"Error Rate: {performance_data['error_rate']:.1%}")
        report.append(f"Uptime Percentage: {performance_data['uptime_percentage']:.1%}")
        
        if performance_data['most_active_hours']:
            report.append(f"Most Active Hours: {', '.join(map(str, performance_data['most_active_hours']))}")
        
        if performance_data['best_performing_subreddits']:
            report.append("Best Performing Subreddits:")
            for subreddit in performance_data['best_performing_subreddits'][:5]:
                report.append(f"  {subreddit}")
        
        report.append("")
        report.append("=" * 60)
        report.append("End of Report")
        
        return "\n".join(report)
    
    def export_comparative_analytics(self, account_ids: List[int], format: str = 'json', days: int = 30) -> Dict[str, Any]:
        """Export comparative analytics for multiple accounts"""
        try:
            if format not in self.supported_formats:
                raise ValueError(f"Unsupported format: {format}")
            
            comparison_data = analytics_engine.get_comparative_analytics(account_ids, days)
            
            export_data = {
                'export_info': {
                    'account_ids': account_ids,
                    'export_date': datetime.utcnow().isoformat(),
                    'period_days': days,
                    'format': format,
                    'export_type': 'comparative_analytics'
                },
                'comparison_data': comparison_data
            }
            
            if format == 'json':
                json_content = json.dumps(export_data, indent=2, default=str)
                filename = f"reddit_comparative_analytics_{len(account_ids)}accounts_{days}days_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
                
                return {
                    'format': 'json',
                    'filename': filename,
                    'content': json_content,
                    'content_type': 'application/json',
                    'size': len(json_content.encode('utf-8'))
                }
            
            # For CSV and PDF, implement similar logic as above
            # This is a simplified version for the demo
            return self.export_account_analytics(account_ids[0], format, days)
            
        except Exception as e:
            logger.error(f"Error exporting comparative analytics: {e}")
            raise

    def export_engagement_logs(self, account_id: int, format: str = 'csv', days: int = 30) -> Dict[str, Any]:
        """Export detailed engagement logs"""
        try:
            from datetime import timedelta
            from models import EngagementLog

            db = SessionLocal()
            account = db.query(RedditAccount).filter(RedditAccount.id == account_id).first()
            if not account:
                raise ValueError(f"Account {account_id} not found")

            # Get engagement logs
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            logs = db.query(EngagementLog).filter(
                EngagementLog.account_id == account_id,
                EngagementLog.timestamp >= cutoff_date
            ).order_by(EngagementLog.timestamp.desc()).all()

            db.close()

            if format == 'csv':
                return self._export_engagement_logs_csv(logs, account.reddit_username, days)
            elif format == 'json':
                return self._export_engagement_logs_json(logs, account.reddit_username, days)
            else:
                raise ValueError(f"Unsupported format for engagement logs: {format}")

        except Exception as e:
            logger.error(f"Error exporting engagement logs: {e}")
            raise

    def _export_engagement_logs_csv(self, logs: List, username: str, days: int) -> Dict[str, Any]:
        """Export engagement logs as CSV"""
        output = StringIO()
        writer = csv.writer(output)

        # Write header
        writer.writerow([
            'Timestamp', 'Action Type', 'Target ID', 'Subreddit',
            'Status', 'Content', 'Score', 'Response Time'
        ])

        # Write data
        for log in logs:
            writer.writerow([
                log.timestamp.isoformat(),
                log.action_type,
                log.target_id,
                log.subreddit,
                log.status,
                (log.content[:100] + '...') if log.content and len(log.content) > 100 else log.content,
                log.score,
                log.response_time
            ])

        csv_content = output.getvalue()
        output.close()

        filename = f"engagement_logs_{username}_{days}days_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"

        return {
            'format': 'csv',
            'filename': filename,
            'content': csv_content,
            'content_type': 'text/csv',
            'size': len(csv_content.encode('utf-8'))
        }

    def _export_engagement_logs_json(self, logs: List, username: str, days: int) -> Dict[str, Any]:
        """Export engagement logs as JSON"""
        logs_data = []
        for log in logs:
            logs_data.append({
                'id': log.id,
                'timestamp': log.timestamp.isoformat(),
                'action_type': log.action_type,
                'target_id': log.target_id,
                'subreddit': log.subreddit,
                'status': log.status,
                'content': log.content,
                'score': log.score,
                'response_time': log.response_time
            })

        export_data = {
            'export_info': {
                'username': username,
                'export_date': datetime.utcnow().isoformat(),
                'period_days': days,
                'total_logs': len(logs_data)
            },
            'engagement_logs': logs_data
        }

        json_content = json.dumps(export_data, indent=2, default=str)
        filename = f"engagement_logs_{username}_{days}days_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"

        return {
            'format': 'json',
            'filename': filename,
            'content': json_content,
            'content_type': 'application/json',
            'size': len(json_content.encode('utf-8'))
        }

    def export_karma_history(self, account_id: int, format: str = 'csv', days: int = 30) -> Dict[str, Any]:
        """Export karma history logs"""
        try:
            from datetime import timedelta
            from models import KarmaLog

            db = SessionLocal()
            account = db.query(RedditAccount).filter(RedditAccount.id == account_id).first()
            if not account:
                raise ValueError(f"Account {account_id} not found")

            # Get karma logs
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            logs = db.query(KarmaLog).filter(
                KarmaLog.account_id == account_id,
                KarmaLog.timestamp >= cutoff_date
            ).order_by(KarmaLog.timestamp.desc()).all()

            db.close()

            if format == 'csv':
                return self._export_karma_history_csv(logs, account.reddit_username, days)
            elif format == 'json':
                return self._export_karma_history_json(logs, account.reddit_username, days)
            else:
                raise ValueError(f"Unsupported format for karma history: {format}")

        except Exception as e:
            logger.error(f"Error exporting karma history: {e}")
            raise

    def _export_karma_history_csv(self, logs: List, username: str, days: int) -> Dict[str, Any]:
        """Export karma history as CSV"""
        output = StringIO()
        writer = csv.writer(output)

        # Write header
        writer.writerow([
            'Timestamp', 'Total Karma', 'Post Karma', 'Comment Karma',
            'Karma Change', 'By Subreddit', 'By Content Type'
        ])

        # Calculate karma changes
        prev_total = 0
        for i, log in enumerate(reversed(logs)):
            karma_change = log.total_karma - prev_total if i > 0 else 0
            prev_total = log.total_karma

            writer.writerow([
                log.timestamp.isoformat(),
                log.total_karma,
                log.post_karma,
                log.comment_karma,
                karma_change,
                json.dumps(log.by_subreddit) if log.by_subreddit else '',
                json.dumps(log.by_content_type) if log.by_content_type else ''
            ])

        csv_content = output.getvalue()
        output.close()

        filename = f"karma_history_{username}_{days}days_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"

        return {
            'format': 'csv',
            'filename': filename,
            'content': csv_content,
            'content_type': 'text/csv',
            'size': len(csv_content.encode('utf-8'))
        }

    def _export_karma_history_json(self, logs: List, username: str, days: int) -> Dict[str, Any]:
        """Export karma history as JSON"""
        logs_data = []
        prev_total = 0

        for i, log in enumerate(reversed(logs)):
            karma_change = log.total_karma - prev_total if i > 0 else 0
            prev_total = log.total_karma

            logs_data.append({
                'id': log.id,
                'timestamp': log.timestamp.isoformat(),
                'total_karma': log.total_karma,
                'post_karma': log.post_karma,
                'comment_karma': log.comment_karma,
                'karma_change': karma_change,
                'by_subreddit': log.by_subreddit,
                'by_content_type': log.by_content_type
            })

        export_data = {
            'export_info': {
                'username': username,
                'export_date': datetime.utcnow().isoformat(),
                'period_days': days,
                'total_logs': len(logs_data)
            },
            'karma_history': logs_data
        }

        json_content = json.dumps(export_data, indent=2, default=str)
        filename = f"karma_history_{username}_{days}days_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"

        return {
            'format': 'json',
            'filename': filename,
            'content': json_content,
            'content_type': 'application/json',
            'size': len(json_content.encode('utf-8'))
        }

export_service = ExportService()
