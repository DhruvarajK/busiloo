# Busiloo

**Busiloo** is a modern, professional public transport management and passenger information system designed specifically for the transit network in Kerala, India. Built with speed and reliability in mind, it provides real-time route finding, bus scheduling, fare estimation, and crowdsourced traffic/crowd reporting.

[![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com/)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-D71F00?style=for-the-badge&logo=sqlalchemy&logoColor=white)](https://www.sqlalchemy.org/)
[![Jinja2](https://img.shields.io/badge/Jinja2-B41717?style=for-the-badge&logo=jinja)](https://palletsprojects.com/p/jinja/)
[![PWA](https://img.shields.io/badge/PWA-5A0FC8?style=for-the-badge&logo=pwa&logoColor=white)](https://web.dev/progressive-web-apps/)

---

## Key Features

### Search and Navigation

- **Point-to-Point Search**: Find direct and transfer bus routes between any two stops in Kerala.
- **Bus Name Search**: Quickly find specific bus services by their names.
- **Nearby Stops**: Utilize GPS to find bus stops and routes in your immediate vicinity.

### Fare and Schedule

- **Dynamic Fare Calculator**: Estimate travel costs based on distance and bus types.
- **Comprehensive Schedules**: Detailed trip timelines showing arrival times at every stop.
- **Trip History**: Keep track of your recently viewed and used trips for quick access.

### Real-time Crowdsourcing

- **Traffic Reporting**: Users can report traffic blocks and severity to help others plan better.
- **Crowd Reports**: View and report bus fullness levels at specific stops and times.
- **Stop Issue Reporting**: Flag incorrect locations, damaged stops, or naming issues.

### Accessibility and Tech

- **Bilingual Interface**: Seamless support for both **English** and **Malayalam**.
- **PWA (Progressive Web App)**: Installable on mobile devices with offline caching via Service Workers.
- **Admin Dashboard**: Robust management interface for administrators to manage buses, routes, stops, and user reports.

---

## Tech Stack

- **Backend**: Python 3.10+ using [FastAPI](https://fastapi.tiangolo.com/)
- **ORM**: [SQLAlchemy](https://www.sqlalchemy.org/)
- **Database Support**: PostgreSQL, MySQL, and SQLite
- **Templating**: Jinja2 with modern CSS (Vanilla)
- **Geodata**: [Overpass API (OpenStreetMap)](https://wiki.openstreetmap.org/wiki/Overpass_API) for stop locations.
- **Security**: JWT-based authentication with `python-jose` and `passlib`.

---

## Getting Started

### Prerequisites

- Python 3.10 or higher
- Pip (Python Package Manager)

### Installation

1. **Clone the repository**:

   ```bash
   git clone https://github.com/your-username/busiloo.git
   cd busiloo
   ```

2. **Set up a virtual environment**:

   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:

   ```bash
   pip install -r requirements.txt
   ```

4. **Environment Configuration**:
   Create a `.env` file in the root directory and add your configurations (Database URLs, Secret Keys, etc.).

5. **Initialize the Database**:
   The application automatically handles table creation on startup via SQLAlchemy.

6. **Run the application**:
   ```bash
   uvicorn main:app --reload
   ```
   The app will be available at `http://localhost:8000`.

### Run with Docker

1. **Build and start the container**:

   ```bash
   docker-compose up --build
   ```

2. The application will be accessible at `http://localhost:8000`.

---

## Project Structure

```text
├── main.py              # Application entry point & core routes
├── models.py            # SQLAlchemy database models
├── schemas.py           # Pydantic models for data validation
├── auth.py              # Security & Authentication logic
├── database.py          # Database connection setup
├── admin.py             # Admin-specific routes
├── public_user.py       # Public user routes and logic
├── union.py             # Union/Reporting specific routes
├── static/              # CSS, JS, and Images
├── templates/           # HTML templates (Jinja2)
├── manifest.json        # PWA manifest
└── service-worker.js    # PWA offline logic
```

---

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request. For major changes, please open an issue first to discuss what you would like to change.

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## License

Distributed under the MIT License. See `LICENSE` for more information. (Note: Please add a LICENSE file if not present).

---

## Support

For any feedback or issues, please use the in-app **Feedback** section or contact us via the repo's issue tracker.

_Powered by the passion for public transit in Kerala._
