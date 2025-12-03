# CourtVision Analytics - Project Summary

## Project Overview
CourtVision Analytics is a predictive analytics platform for NBA fans that uses historical data to forecast game outcomes, visualized through interactive dashboards and accessible via a secure user portal.

---

## Table 1: Foundational Topics (15 pts)

| # | Topic | Status | Implementation Details |
|---|-------|--------|----------------------|
| 1 | GitHub Repository & Environment Setup | ✅ Complete | Public repo with proper .gitignore, virtual environment, Django 4.2+, feature branches |
| 2 | Wizard of Oz Prototyping / UI/UX Planning | ✅ Complete | Wireframes in /wireframes/v1/ folder (dashboard.png, login.png, core_feature.png, error_state.png) |
| 3 | Models + ORM Basics | ✅ Complete | Team, Player, Game, UserPick, UserProfile models with migrations and admin registration |
| 4 | Views + Templates + URLs | ✅ Complete | FBVs and CBVs (ListView, DetailView), template inheritance, proper URL namespacing |
| 5 | User Authentication for Internal Users | ✅ Complete | Login/Logout views, @login_required protection, instructor (mohitg2) and guest (infoadmins) accounts |
| 6 | Deployment (Production Setup) | ✅ Complete | Split settings (base.py, development.py, production.py), PythonAnywhere ready |

---

## Table 2: Functional Add-ons (15+ pts)

| # | Topic | Status | Implementation Details |
|---|-------|--------|----------------------|
| 1 | ORM Queries + Data Summaries | ✅ Complete | Aggregations for leaderboards, team stats, prediction accuracy calculations in views.py |
| 2 | Static Files (CSS/JS Integration) | ✅ Complete | Bootstrap 5, custom CSS in /static/css/style.css, proper STATIC_ROOT configuration |
| 3 | Charts / Visualization (Matplotlib) | ✅ Complete | Team comparison bar charts generated with Matplotlib, embedded as base64 images |
| 4 | Forms + Basic Input / CRUD | ✅ Complete | UserPickForm for game predictions, ExportForm for data downloads |
| 6 | Integrate External APIs | ✅ Complete | NBA API service (balldontlie.io) in core/services/nba_api.py with sync commands |
| 7 | Data Presentation & Export | ✅ Complete | CSV and JSON export functionality for predictions data |
| 8 | User Authentication for External Users | ✅ Complete | Public signup with UserCreationForm, auto-login, UserProfile creation |
| 9 | External Databases Integration | ✅ Complete | PostgreSQL configuration in production.py with environment variables |

**Total Add-on Topics: 8 (3 bonus topics)**

---

## Features Summary

### Core Features
- **Home Page**: Landing page with featured game, upcoming games preview, conference standings
- **Dashboard**: Today's games with predictions, upcoming games, recent results
- **Team Pages**: Team list by conference, team detail with roster and stats
- **Game Detail**: Predictions display, team comparison chart, community voting
- **Analytics**: Leaderboards, model accuracy, top predictors
- **Data Export**: Download predictions as CSV or JSON

### Authentication
- Internal instructor account: mohitg2 / graingerlibrary
- Internal guest account: infoadmins / uiucinfo
- Public user registration

### Technical Stack
- Django 4.2+
- Bootstrap 5 (responsive UI)
- Matplotlib (charts)
- PostgreSQL (production)
- SQLite (development)

---

## File Structure
```
final_project/
├── courtvision/          # Project settings
│   └── settings/         # Split settings (base, dev, prod)
├── core/                 # Main app
│   ├── models.py         # Data models
│   ├── views.py          # View functions
│   ├── services/         # NBA API integration
│   └── management/       # Custom commands
├── accounts/             # Authentication
├── templates/            # HTML templates
├── static/               # CSS, JS, images
├── docs/                 # Documentation
└── wireframes/           # UI prototypes
```

---

## Deployment
- **Platform**: PythonAnywhere
- **URL**: [To be updated after deployment]
- **Static Files**: Configured with collectstatic
- **Database**: SQLite (free tier) / PostgreSQL (paid)

---

*Generated for INFO 390 Final Project*
