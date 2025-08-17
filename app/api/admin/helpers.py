from datetime import datetime

def get_category_color(category_name):
    """Helper to assign consistent colors to categories"""
    colors = {
        'Food & Dining': '#10B981',
        'Fashion': '#3B82F6',
        'Electronics': '#8B5CF6',
        'Books': '#F59E0B',
        'Other': '#EF4444'
    }
    return colors.get(category_name, '#6B7280')

def format_timesince(dt):
    """Format datetime as 'X time ago' string"""
    now = datetime.now()
    diff = now - dt
    
    if diff.days > 0:
        return f"{diff.days} day{'s' if diff.days > 1 else ''} ago"
    hours = diff.seconds // 3600
    if hours > 0:
        return f"{hours} hour{'s' if hours > 1 else ''} ago"
    minutes = diff.seconds // 60
    return f"{minutes} minute{'s' if minutes > 1 else ''} ago"