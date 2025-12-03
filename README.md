# CourtVision Analytics

A predictive analytics platform for NBA fans and bettors that uses historical data to forecast game outcomes, visualized through interactive dashboards and accessible via a secure user portal.

## Features

### Part 1: Foundational Requirements
- **Django Project Structure**: Split settings (base.py, development.py, production.py)
- **Models & ORM**: Team, Game, Player, UserPick, UserProfile models
- **Views & Templates**: Home page, Dashboard, Team Detail, Game Detail views
- **Authentication**: Login, Logout, and Public Signup with @login_required protection
- **Deployment Ready**: Configured for PythonAnywhere deployment

### Part 2: Functional Add-ons
1. **External Database Integration**: PostgreSQL configuration for production
2. **External API Integration**: balldontlie.io NBA API for live data
3. **Data Export**: CSV and JSON export functionality
4. **Charts/Visualization**: Matplotlib charts for team comparisons
5. **ORM Queries**: Advanced aggregations for leaderboards and statistics
6. **User Forms**: Community voting/prediction system
7. **Public Signup**: User registration for all visitors

## Quick Start

### 1. Clone and Setup Environment
```bash
cd final_project
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Run Migrations
```bash
python manage.py migrate
```

### 3. Load Sample Data
```bash
python manage.py load_sample_data
python manage.py create_instructor
```

### 4. Create Superuser (Optional)
```bash
python manage.py createsuperuser
```

### 5. Run Development Server
```bash
python manage.py runserver
```

Visit http://127.0.0.1:8000/ to access the application.

## Credentials

### Instructor Account
- **Username**: mohitg2
- **Password**: graingerlibrary

## Project Structure

```
final_project/
├── courtvision/           # Project settings
│   ├── settings/
│   │   ├── base.py        # Shared settings
│   │   ├── development.py # Development settings
│   │   └── production.py  # Production settings
│   ├── urls.py
│   └── wsgi.py
├── core/                  # Main application
│   ├── models.py          # Team, Game, Player, UserPick models
│   ├── views.py           # All view functions
│   ├── forms.py           # UserPickForm, ExportForm
│   ├── admin.py           # Admin configurations
│   ├── urls.py
│   ├── services/          # NBA API service
│   ├── templatetags/      # Custom template tags
│   └── management/        # Management commands
├── accounts/              # Authentication app
│   ├── views.py           # Login, Logout, Signup views
│   ├── forms.py           # Custom auth forms
│   └── urls.py
├── templates/             # HTML templates
│   ├── base.html
│   ├── core/
│   └── accounts/
├── static/                # Static files (CSS, JS, images)
├── manage.py
└── requirements.txt
```

## Management Commands

```bash
# Load sample NBA data (teams, players, games)
python manage.py load_sample_data

# Create instructor account
python manage.py create_instructor

# Sync data from NBA API (requires API key for full functionality)
python manage.py sync_nba_data --api-key YOUR_API_KEY
```

## PythonAnywhere Deployment

1. Upload your project to PythonAnywhere
2. Set environment variables:
   - `DJANGO_SETTINGS_MODULE=courtvision.settings.production`
   - `DJANGO_SECRET_KEY=your-secret-key`
   - Database credentials if using PostgreSQL
3. Update `ALLOWED_HOSTS` in production.py with your domain
4. Run `python manage.py collectstatic`
5. Configure WSGI file to point to `courtvision.wsgi`

## Technologies Used

- Django 4.2+
- Bootstrap 5
- Matplotlib for charts
- PostgreSQL (production)
- SQLite (development)

## License

This project is for educational purposes as part of INFO 390.
