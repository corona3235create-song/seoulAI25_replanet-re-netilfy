# Replanet Project Guide

This guide provides instructions for setting up and running the Replanet project locally.

## 1. Project Overview & Tech Stack

-   **Service Name:** Replanet - Eco Challenge and Carbon Reduction Management Service.
-   **Backend:** Python 3.11, FastAPI, SQLAlchemy, SQLite (ecooo.db).
-   **Frontend:** React (npm/yarn).

## 2. Core Principles

-   **Local & Free Service:** This setup removes all AWS dependencies, focusing on local or free hosting environments.
-   **Existing Logic Preservation:** Core business logic remains intact.
-   **Resource Efficiency:** Optimized code and minimal resource consumption.

## 3. Local Development Environment Setup

### 3.1. Common Requirements

-   **Python:** Version 3.11 or higher.
-   **Node.js & npm/yarn:** For frontend development.
-   **.env file:** Located in the project root. This file contains necessary environment variables for both backend and frontend.

### 3.2. Backend Setup & Execution

1.  **Navigate to Backend Directory:**
    ```bash
    cd backend
    ```

2.  **Create and Activate Virtual Environment:**
    ```bash
    python -m venv venv
    .\venv\Scripts\activate  # On Windows
    # source venv/bin/activate # On Linux/macOS
    ```
    (You should see `(venv)` prefix in your terminal after activation)

3.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configure Environment Variables (`.env` in project root):**
    Ensure the following variables are set in the **project root's** `.env` file:
    ```
    # Example .env content
    SECRET_KEY="YOUR_SUPER_SECRET_KEY_HERE"
    ALGORITHM="HS256"
    
    # OpenAI API Key for AI chatbot functionality
    OPENAI_API_KEY="YOUR_OPENAI_API_KEY"
    
    # Google Custom Search API Keys for web search functionality (Optional)
    GOOGLE_API_KEY="YOUR_GOOGLE_API_KEY"
    GOOGLE_CSE_ID="YOUR_GOOGLE_CSE_ID"
    ```
    *Note: The backend is configured to use a local SQLite database located at `backend/database/ecooo.db`. This database will be automatically created and initialized with schema and seed data (including admin and test users) when the server starts for the first time.*

5.  **Run Backend Server:**
    ```bash
    uvicorn backend.main:app --host 0.0.0.0 --port 8080 --reload
    ```
    The backend server will run on `http://localhost:8080`.

### 3.3. Frontend Setup & Execution

1.  **Navigate to Frontend Directory:**
    ```bash
    cd frontend
    ```

2.  **Install Dependencies:**
    ```bash
    npm install
    # or yarn install
    ```

3.  **Configure Environment Variables (`.env` in frontend directory):**
    Create a `.env` file in the `frontend/` directory and set the API URL:
    ```
    REACT_APP_API_URL=http://localhost:8080
    ```

4.  **Run Frontend Server:**
    ```bash
    npm start
    # or yarn start
    ```
    The frontend application will typically open in your browser at `http://localhost:3000`.

## 4. Key Accounts

-   **Admin User:**
    -   ID: `admin@admin`
    -   Password: `12345678`
-   **Test User:**
    -   ID: `test@gmail.com`
    -   Password: `1234`

## 5. Additional Information

-   **Local Reports:** Generated PDF reports are saved in `backend/reports/` and can be accessed via `http://localhost:8080/reports/<filename>`.