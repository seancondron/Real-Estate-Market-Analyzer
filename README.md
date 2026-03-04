# CS Project

## Stack
- **Frontend**: 
- **Backend**: Pandas, Numpy, Scikit-learn
- **Database**: Supabase

## Setup

1. Clone the repo
   ```bash
   git clone https://github.com/your-username/cs-project.git
   cd cs-project
   ```

2. Create a virtual environment
   ```bash
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   ```

3. Install dependencies
   ```bash
   pip install -r requirements.txt
   ```

4. Set up environment variables
   ```bash
   cp .env.example .env
   # Fill in your Supabase credentials in .env
   ```

5. Run the app
   ```bash
   streamlit run frontend/app.py
   ```

## Branch Workflow
```bash
git checkout main && git pull
git checkout -b feature/your-name-feature
# make changes
git add .
git commit -m "feat: describe your change"
git push origin feature/your-name-feature
# open a Pull Request into main on GitHub
```
