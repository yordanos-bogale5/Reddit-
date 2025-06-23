"""
Data visualization service for Reddit automation dashboard
Prepares chart data for various visualization types
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
import json

from analytics_engine import analytics_engine
from database import SessionLocal
from models import KarmaLog, EngagementLog, ActivityLog

logger = logging.getLogger(__name__)

@dataclass
class ChartDataPoint:
    """Single data point for charts"""
    x: Any  # Usually date/time or category
    y: float
    label: Optional[str] = None
    color: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

@dataclass
class ChartDataset:
    """Dataset for charts"""
    label: str
    data: List[ChartDataPoint]
    chart_type: str  # 'line', 'bar', 'pie', 'doughnut', 'area'
    color: Optional[str] = None
    background_color: Optional[str] = None
    border_color: Optional[str] = None

@dataclass
class ChartConfig:
    """Complete chart configuration"""
    title: str
    datasets: List[ChartDataset]
    chart_type: str
    x_axis_label: Optional[str] = None
    y_axis_label: Optional[str] = None
    options: Optional[Dict[str, Any]] = None

class VisualizationService:
    """Service for preparing chart data"""
    
    def __init__(self):
        self.color_palette = [
            '#3B82F6', '#EF4444', '#10B981', '#F59E0B', '#8B5CF6',
            '#06B6D4', '#F97316', '#84CC16', '#EC4899', '#6366F1'
        ]
    
    def prepare_karma_growth_chart(self, account_id: int, days: int = 30) -> ChartConfig:
        """Prepare karma growth line chart data"""
        try:
            time_series_data = analytics_engine.get_time_series_data(account_id, 'karma', days)
            
            # Prepare datasets for total, post, and comment karma
            datasets = []
            
            if time_series_data:
                # Total karma line
                total_karma_points = [
                    ChartDataPoint(
                        x=item['date'],
                        y=item['total_karma'],
                        metadata={'date': item['date']}
                    )
                    for item in time_series_data
                ]
                
                datasets.append(ChartDataset(
                    label='Total Karma',
                    data=total_karma_points,
                    chart_type='line',
                    color=self.color_palette[0],
                    border_color=self.color_palette[0],
                    background_color=f"{self.color_palette[0]}20"
                ))
                
                # Post karma line
                post_karma_points = [
                    ChartDataPoint(
                        x=item['date'],
                        y=item['post_karma'],
                        metadata={'date': item['date']}
                    )
                    for item in time_series_data
                ]
                
                datasets.append(ChartDataset(
                    label='Post Karma',
                    data=post_karma_points,
                    chart_type='line',
                    color=self.color_palette[1],
                    border_color=self.color_palette[1],
                    background_color=f"{self.color_palette[1]}20"
                ))
                
                # Comment karma line
                comment_karma_points = [
                    ChartDataPoint(
                        x=item['date'],
                        y=item['comment_karma'],
                        metadata={'date': item['date']}
                    )
                    for item in time_series_data
                ]
                
                datasets.append(ChartDataset(
                    label='Comment Karma',
                    data=comment_karma_points,
                    chart_type='line',
                    color=self.color_palette[2],
                    border_color=self.color_palette[2],
                    background_color=f"{self.color_palette[2]}20"
                ))
            
            return ChartConfig(
                title=f'Karma Growth - Last {days} Days',
                datasets=datasets,
                chart_type='line',
                x_axis_label='Date',
                y_axis_label='Karma Points',
                options={
                    'responsive': True,
                    'scales': {
                        'x': {'type': 'time', 'time': {'unit': 'day'}},
                        'y': {'beginAtZero': True}
                    }
                }
            )
            
        except Exception as e:
            logger.error(f"Error preparing karma growth chart: {e}")
            return ChartConfig(
                title='Karma Growth Chart',
                datasets=[],
                chart_type='line'
            )
    
    def prepare_engagement_chart(self, account_id: int, days: int = 30) -> ChartConfig:
        """Prepare engagement activity chart"""
        try:
            engagement_metrics = analytics_engine.get_engagement_analytics(account_id, days)
            
            # Prepare pie chart for action types
            action_data = []
            colors = []
            
            for i, (action_type, count) in enumerate(engagement_metrics.actions_by_type.items()):
                action_data.append(ChartDataPoint(
                    x=action_type.title(),
                    y=count,
                    label=action_type.title(),
                    color=self.color_palette[i % len(self.color_palette)]
                ))
                colors.append(self.color_palette[i % len(self.color_palette)])
            
            dataset = ChartDataset(
                label='Actions by Type',
                data=action_data,
                chart_type='doughnut',
                background_color=colors,
                border_color=colors
            )
            
            return ChartConfig(
                title=f'Engagement by Action Type - Last {days} Days',
                datasets=[dataset],
                chart_type='doughnut',
                options={
                    'responsive': True,
                    'plugins': {
                        'legend': {'position': 'bottom'}
                    }
                }
            )
            
        except Exception as e:
            logger.error(f"Error preparing engagement chart: {e}")
            return ChartConfig(
                title='Engagement Chart',
                datasets=[],
                chart_type='doughnut'
            )
    
    def prepare_subreddit_performance_chart(self, account_id: int, days: int = 30) -> ChartConfig:
        """Prepare subreddit performance bar chart"""
        try:
            subreddit_analytics = analytics_engine.get_subreddit_analytics(account_id, days)
            subreddit_performance = subreddit_analytics.get('subreddit_performance', {})
            
            # Get top 10 subreddits by engagement score
            sorted_subreddits = sorted(
                subreddit_performance.items(),
                key=lambda x: x[1].get('engagement_score', 0),
                reverse=True
            )[:10]
            
            # Prepare bar chart data
            subreddit_points = []
            colors = []
            
            for i, (subreddit, data) in enumerate(sorted_subreddits):
                subreddit_points.append(ChartDataPoint(
                    x=subreddit,
                    y=data.get('engagement_score', 0),
                    label=subreddit,
                    metadata={
                        'total_actions': data.get('total_actions', 0),
                        'success_rate': data.get('success_rate', 0)
                    }
                ))
                colors.append(self.color_palette[i % len(self.color_palette)])
            
            dataset = ChartDataset(
                label='Engagement Score',
                data=subreddit_points,
                chart_type='bar',
                background_color=colors,
                border_color=colors
            )
            
            return ChartConfig(
                title=f'Top Subreddit Performance - Last {days} Days',
                datasets=[dataset],
                chart_type='bar',
                x_axis_label='Subreddit',
                y_axis_label='Engagement Score',
                options={
                    'responsive': True,
                    'scales': {
                        'y': {'beginAtZero': True}
                    },
                    'plugins': {
                        'legend': {'display': False}
                    }
                }
            )
            
        except Exception as e:
            logger.error(f"Error preparing subreddit performance chart: {e}")
            return ChartConfig(
                title='Subreddit Performance Chart',
                datasets=[],
                chart_type='bar'
            )
    
    def prepare_activity_heatmap(self, account_id: int, days: int = 30) -> ChartConfig:
        """Prepare activity heatmap data"""
        try:
            engagement_metrics = analytics_engine.get_engagement_analytics(account_id, days)
            hourly_distribution = engagement_metrics.hourly_distribution
            
            # Prepare heatmap data (24 hours x 7 days)
            heatmap_data = []
            days_of_week = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
            
            # For simplicity, we'll create a basic hourly activity chart
            # In a real implementation, you'd want day-of-week breakdown
            hourly_points = []
            
            for hour in range(24):
                activity_count = hourly_distribution.get(hour, 0)
                hourly_points.append(ChartDataPoint(
                    x=f"{hour:02d}:00",
                    y=activity_count,
                    metadata={'hour': hour, 'activity_count': activity_count}
                ))
            
            dataset = ChartDataset(
                label='Activity by Hour',
                data=hourly_points,
                chart_type='bar',
                color=self.color_palette[0],
                background_color=self.color_palette[0],
                border_color=self.color_palette[0]
            )
            
            return ChartConfig(
                title=f'Activity Heatmap - Last {days} Days',
                datasets=[dataset],
                chart_type='bar',
                x_axis_label='Hour of Day',
                y_axis_label='Activity Count',
                options={
                    'responsive': True,
                    'scales': {
                        'y': {'beginAtZero': True}
                    }
                }
            )
            
        except Exception as e:
            logger.error(f"Error preparing activity heatmap: {e}")
            return ChartConfig(
                title='Activity Heatmap',
                datasets=[],
                chart_type='bar'
            )
    
    def prepare_success_rate_trend(self, account_id: int, days: int = 30) -> ChartConfig:
        """Prepare success rate trend chart"""
        try:
            time_series_data = analytics_engine.get_time_series_data(account_id, 'engagement', days)
            
            # Prepare success rate line chart
            success_rate_points = []
            
            for item in time_series_data:
                success_rate = item.get('success_rate', 0) * 100  # Convert to percentage
                success_rate_points.append(ChartDataPoint(
                    x=item['date'],
                    y=success_rate,
                    metadata={
                        'date': item['date'],
                        'total_actions': item.get('total_actions', 0),
                        'successful_actions': item.get('successful_actions', 0)
                    }
                ))
            
            dataset = ChartDataset(
                label='Success Rate (%)',
                data=success_rate_points,
                chart_type='line',
                color=self.color_palette[2],
                border_color=self.color_palette[2],
                background_color=f"{self.color_palette[2]}20"
            )
            
            return ChartConfig(
                title=f'Success Rate Trend - Last {days} Days',
                datasets=[dataset],
                chart_type='line',
                x_axis_label='Date',
                y_axis_label='Success Rate (%)',
                options={
                    'responsive': True,
                    'scales': {
                        'x': {'type': 'time', 'time': {'unit': 'day'}},
                        'y': {'beginAtZero': True, 'max': 100}
                    }
                }
            )
            
        except Exception as e:
            logger.error(f"Error preparing success rate trend: {e}")
            return ChartConfig(
                title='Success Rate Trend',
                datasets=[],
                chart_type='line'
            )

    def prepare_comparative_chart(self, account_ids: List[int], metric: str, days: int = 30) -> ChartConfig:
        """Prepare comparative chart for multiple accounts"""
        try:
            comparison_data = analytics_engine.get_comparative_analytics(account_ids, days)
            accounts_data = comparison_data.get('accounts_data', {})

            datasets = []

            if metric == 'karma_growth':
                # Prepare bar chart for karma growth comparison
                account_points = []
                colors = []

                for i, (account_id, data) in enumerate(accounts_data.items()):
                    account_points.append(ChartDataPoint(
                        x=data.get('username', f'Account {account_id}'),
                        y=data.get('karma_growth_rate', 0),
                        metadata=data
                    ))
                    colors.append(self.color_palette[i % len(self.color_palette)])

                dataset = ChartDataset(
                    label='Daily Karma Growth Rate',
                    data=account_points,
                    chart_type='bar',
                    background_color=colors,
                    border_color=colors
                )

                return ChartConfig(
                    title=f'Karma Growth Comparison - Last {days} Days',
                    datasets=[dataset],
                    chart_type='bar',
                    x_axis_label='Account',
                    y_axis_label='Daily Growth Rate',
                    options={'responsive': True, 'plugins': {'legend': {'display': False}}}
                )

            elif metric == 'success_rate':
                # Prepare bar chart for success rate comparison
                account_points = []
                colors = []

                for i, (account_id, data) in enumerate(accounts_data.items()):
                    success_rate = data.get('success_rate', 0) * 100
                    account_points.append(ChartDataPoint(
                        x=data.get('username', f'Account {account_id}'),
                        y=success_rate,
                        metadata=data
                    ))
                    colors.append(self.color_palette[i % len(self.color_palette)])

                dataset = ChartDataset(
                    label='Success Rate (%)',
                    data=account_points,
                    chart_type='bar',
                    background_color=colors,
                    border_color=colors
                )

                return ChartConfig(
                    title=f'Success Rate Comparison - Last {days} Days',
                    datasets=[dataset],
                    chart_type='bar',
                    x_axis_label='Account',
                    y_axis_label='Success Rate (%)',
                    options={'responsive': True, 'plugins': {'legend': {'display': False}}}
                )

            return ChartConfig(
                title='Comparative Chart',
                datasets=[],
                chart_type='bar'
            )

        except Exception as e:
            logger.error(f"Error preparing comparative chart: {e}")
            return ChartConfig(
                title='Comparative Chart',
                datasets=[],
                chart_type='bar'
            )

    def prepare_dashboard_overview_charts(self, account_id: int = None) -> Dict[str, ChartConfig]:
        """Prepare all charts for dashboard overview"""
        try:
            charts = {}

            if account_id:
                # Single account dashboard
                charts['karma_growth'] = self.prepare_karma_growth_chart(account_id, 30)
                charts['engagement'] = self.prepare_engagement_chart(account_id, 30)
                charts['subreddit_performance'] = self.prepare_subreddit_performance_chart(account_id, 30)
                charts['activity_heatmap'] = self.prepare_activity_heatmap(account_id, 30)
                charts['success_rate_trend'] = self.prepare_success_rate_trend(account_id, 30)
            else:
                # Multi-account dashboard
                summary = analytics_engine.get_dashboard_summary()

                # Prepare summary charts
                charts['accounts_overview'] = self.prepare_accounts_overview_chart()
                charts['total_activity'] = self.prepare_total_activity_chart()

            return charts

        except Exception as e:
            logger.error(f"Error preparing dashboard overview charts: {e}")
            return {}

    def prepare_accounts_overview_chart(self) -> ChartConfig:
        """Prepare accounts overview chart"""
        try:
            from database import SessionLocal
            from models import RedditAccount, AutomationSettings

            db = SessionLocal()

            # Get account statistics
            total_accounts = db.query(RedditAccount).count()
            active_automations = db.query(RedditAccount).join(AutomationSettings).filter(
                (AutomationSettings.auto_upvote_enabled == True) |
                (AutomationSettings.auto_comment_enabled == True) |
                (AutomationSettings.auto_post_enabled == True)
            ).count()
            inactive_accounts = total_accounts - active_automations

            db.close()

            # Prepare pie chart
            overview_data = [
                ChartDataPoint(x='Active', y=active_automations, label='Active Automation', color=self.color_palette[2]),
                ChartDataPoint(x='Inactive', y=inactive_accounts, label='Inactive', color=self.color_palette[3])
            ]

            dataset = ChartDataset(
                label='Account Status',
                data=overview_data,
                chart_type='doughnut',
                background_color=[self.color_palette[2], self.color_palette[3]],
                border_color=[self.color_palette[2], self.color_palette[3]]
            )

            return ChartConfig(
                title='Accounts Overview',
                datasets=[dataset],
                chart_type='doughnut',
                options={'responsive': True, 'plugins': {'legend': {'position': 'bottom'}}}
            )

        except Exception as e:
            logger.error(f"Error preparing accounts overview chart: {e}")
            return ChartConfig(title='Accounts Overview', datasets=[], chart_type='doughnut')

    def prepare_total_activity_chart(self, days: int = 7) -> ChartConfig:
        """Prepare total activity chart for all accounts"""
        try:
            from database import SessionLocal
            from sqlalchemy import func

            db = SessionLocal()
            start_date = datetime.utcnow() - timedelta(days=days)

            # Get daily activity counts
            daily_activity = db.query(
                func.date(EngagementLog.timestamp).label('date'),
                func.count(EngagementLog.id).label('activity_count')
            ).filter(
                EngagementLog.timestamp >= start_date
            ).group_by(func.date(EngagementLog.timestamp)).all()

            db.close()

            # Prepare line chart data
            activity_points = []
            for row in daily_activity:
                activity_points.append(ChartDataPoint(
                    x=row.date.strftime('%Y-%m-%d'),
                    y=row.activity_count,
                    metadata={'date': row.date.strftime('%Y-%m-%d')}
                ))

            dataset = ChartDataset(
                label='Total Activity',
                data=activity_points,
                chart_type='line',
                color=self.color_palette[0],
                border_color=self.color_palette[0],
                background_color=f"{self.color_palette[0]}20"
            )

            return ChartConfig(
                title=f'Total Activity - Last {days} Days',
                datasets=[dataset],
                chart_type='line',
                x_axis_label='Date',
                y_axis_label='Activity Count',
                options={
                    'responsive': True,
                    'scales': {
                        'x': {'type': 'time', 'time': {'unit': 'day'}},
                        'y': {'beginAtZero': True}
                    }
                }
            )

        except Exception as e:
            logger.error(f"Error preparing total activity chart: {e}")
            return ChartConfig(title='Total Activity', datasets=[], chart_type='line')

    def convert_chart_to_chartjs_format(self, chart_config: ChartConfig) -> Dict[str, Any]:
        """Convert ChartConfig to Chart.js format"""
        try:
            chartjs_data = {
                'type': chart_config.chart_type,
                'data': {
                    'labels': [],
                    'datasets': []
                },
                'options': chart_config.options or {}
            }

            # Set default title
            if 'plugins' not in chartjs_data['options']:
                chartjs_data['options']['plugins'] = {}
            if 'title' not in chartjs_data['options']['plugins']:
                chartjs_data['options']['plugins']['title'] = {
                    'display': True,
                    'text': chart_config.title
                }

            for dataset in chart_config.datasets:
                # Extract labels from first dataset
                if not chartjs_data['data']['labels'] and dataset.data:
                    chartjs_data['data']['labels'] = [point.x for point in dataset.data]

                # Convert dataset
                chartjs_dataset = {
                    'label': dataset.label,
                    'data': [point.y for point in dataset.data]
                }

                # Add styling
                if dataset.background_color:
                    chartjs_dataset['backgroundColor'] = dataset.background_color
                if dataset.border_color:
                    chartjs_dataset['borderColor'] = dataset.border_color
                if dataset.color:
                    chartjs_dataset['borderColor'] = dataset.color

                chartjs_data['data']['datasets'].append(chartjs_dataset)

            return chartjs_data

        except Exception as e:
            logger.error(f"Error converting chart to Chart.js format: {e}")
            return {'type': 'line', 'data': {'labels': [], 'datasets': []}, 'options': {}}

visualization_service = VisualizationService()
