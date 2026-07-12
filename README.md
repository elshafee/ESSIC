# ESSIC — Electronic Services & Scientific Creativity Center
## Document Numbering & Management System

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.0.3-green?logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Production-brightgreen)](https://essic-3fty.vercel.app/)

---

## 🎯 Overview

**ESSIC** is a professional document management system designed for offices and organizations that need to generate sequential document numbers, insert them into Word templates, and maintain a comprehensive audit trail. Built with Flask and SQLAlchemy, it provides secure multi-user access, role-based permissions, TOTP two-factor authentication, and AI-powered document composition.

The system is currently **deployed and live** at: [https://essic-3fty.vercel.app/](https://essic-3fty.vercel.app/)

### Key Features
- 📄 **Document Numbering**: Automatic sequential numbering with month/year reset
- 📝 **Template Processing**: Replace placeholders in Word (.docx) documents safely
- 🔐 **Security**: TOTP-based two-factor authentication for all users
- 👥 **Role-Based Access Control**: Admin and user roles with granular permissions
- 🗂️ **Document History**: Full audit trail of all generated documents
- ☁️ **Cloud Storage**: OneDrive integration for document backup
- 🤖 **AI Generation**: Powered by Gemini, Groq, and OpenAI for Arabic document composition
- 📱 **Responsive UI**: Mobile-friendly interface with Bootstrap styling
- 💾 **Multi-Format Output**: Generate both .docx and .pdf outputs

---

## 📋 Technical Stack

| Component | Technology |
|-----------|-----------|
| **Backend Framework** | Flask 3.0.3 |
| **ORM** | SQLAlchemy 2.0.49 |
| **Database** | PostgreSQL (Supabase) |
| **Authentication** | TOTP (PyOTP), MSAL |
| **Document Processing** | python-docx, lxml |
| **PDF Generation** | docx2pdf, dxpdf |
| **AI Integration** | Google Generative AI, Groq, OpenAI |
| **Frontend** | HTML5, Bootstrap, Jinja2 |
| **Deployment** | Vercel (with temporary file storage) |

---

## 🚀 Getting Started

### Prerequisites
- **Python 3.10 or higher**
- **pip** (Python package manager)
- **Environment variables** (see Configuration section)

### 1. Clone the Repository
```bash
git clone https://github.com/elshafee/ESSIC.git
cd ESSIC/flask
```

### 2. Create a Virtual Environment
```bash
python -m venv venv

# On Windows:
venv\Scripts\activate

# On macOS/Linux:
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables
Create a `.env` file in the `flask/` directory:

```env
# Database (PostgreSQL via Supabase)
SUPABASE_DB_URL=postgresql+psycopg://user:password@db.host/dbname

# Admin & Allowed Users (comma-separated emails)
ADMIN_EMAILS=admin@example.com,super.admin@example.com
ALLOWED_EMAILS=user1@example.com,user2@example.com

# Optional: OneDrive Integration
ONEDRIVE_SHARE_URL=https://your-onedrive-share-url

# Optional: AI Model API Keys (user-configurable in settings)
# GEMINI_API_KEY, GROQ_API_KEY, DEEPSEEK_API_KEY configured per-user

# Deployment
VERCEL=0  # Set to 1 when deploying on Vercel
DATA_DIR=/tmp  # Temporary directory for files (Vercel uses /tmp)
```

### 5. Run the Application

**Local Development:**
```bash
python app.py
```
The app will start at `http://localhost:5010`

**Production (Vercel):**
```bash
vercel deploy
```

---

## 📁 Project Structure

```
flask/
├── app.py                      # Flask application & route definitions
├── models.py                   # SQLAlchemy database models (Document, User)
├── requirements.txt            # Python dependencies
│
├── services/
│   ├── numbering.py           # Serial number generation & formatting
│   ├── word_editor.py         # Safe .docx placeholder replacement
│   ├── pdf_converter.py       # DOCX to PDF conversion
│   ├── ai_generator.py        # Arabic text generation with LLMs
│   ├── onedrive.py            # OneDrive file upload/download
│   └── __init__.py
│
├── templates/
│   ├── base.html              # Base layout (navigation, sidebar, alerts)
│   ├── login.html             # Login page
│   ├── setup.html             # 2FA QR code setup
│   ├── verify.html            # 2FA code verification
│   ├── index.html             # Main upload & number preview
│   ├── documents.html         # Document history & management
│   ├── edit.html              # Edit document & regenerate
│   ├── users.html             # User management (admin)
│   ├── settings.html          # User settings & API keys
│   ├── ai_step1.html          # AI: document type selection
│   ├── ai_step2.html          # AI: composition form
│   └── ai_step3.html          # AI: preview & finalization
│
├── static/
│   ├── css/                   # Bootstrap & custom styling
│   ├── js/                    # Client-side scripts
│   └── images/                # ESSIC logo & icons
│
└── template_essic.docx        # Default .docx template for direct generation
```

---

## 📖 Usage Guide

### For Regular Users

#### 1. Login
- Navigate to the application
- Enter your email address
- Complete TOTP (two-factor authentication) verification
- Access the dashboard

#### 2. Generate a Document Number
**Option A: Upload Your Template**
- Click **"Upload Document"**
- Select your .docx file
- Add a title (optional)
- Preview the generated code
- Click **"Generate"**
- Download the numbered document

**Option B: Use Direct Template**
- Click **"Use Direct Template"**
- Fill in document details:
  - Recipient office
  - Subject line
  - Holder's name & position
  - Document body
  - Sender (optional)
- Preview & confirm
- Document auto-generates with sequential number

#### 3. Manage Documents
- View all your generated documents in **"Documents"** tab
- Download .docx or .pdf versions
- Edit serial number (regenerate with new code)
- Delete records

### For Administrators

#### User Management
- Click **"Users"** (admin panel)
- **Add User**: Create new accounts with auto-generated TOTP
- **Edit User**: Modify names, roles, reset 2FA
- **Toggle Role**: Switch between admin/user permissions
- **Delete User**: Remove access (cannot delete root admins)

#### Document Approval
- View all documents (users and admins combined)
- **Approve**: Move pending documents to approved status & upload to OneDrive
- **Reject**: Return documents to users for revision
- Auto-generate PDFs during approval if missing

#### Settings
- Manage API keys for AI models (Gemini, Groq, DeepSeek)
- Configure OneDrive integration
- Monitor document statistics

---

## 🔢 Document Number Format

All generated documents follow this format:

```
Code No 0042 ESSIC 07-2026
       ↑    ↑     ↑  ↑
       │    │     │  └─ Current Month-Year
       │    │     └───── Organization ID
       │    └─────────── Sequential number (zero-padded, resets monthly)
       └──────────────── Fixed prefix
```

**Numbering Logic:**
- Sequential counter increments within each month/year combination
- Counter resets automatically on the first document of a new month
- Edited documents retain their original serial number unless manually changed
- Duplicate serials within a month are prevented by database constraints

---

## 🔐 Security Features

### Authentication & Authorization
- **TOTP (Time-based One-Time Password)**: All users must enable 2FA on first login
- **Session Management**: User sessions expire and prevent unauthorized access
- **Role-Based Access Control (RBAC)**:
  - `user`: Can upload templates, generate documents, view own history
  - `admin`: Full access to all documents, user management, settings

### Data Protection
- **Password-less Login**: Email-based authentication (no passwords stored)
- **Environment Secrets**: Sensitive data stored in `.env` (never committed)
- **CSRF Protection**: All forms include Flask CSRF tokens
- **Secure File Handling**: Input validation, secure filename sanitization
- **API Key Encryption**: LLM API keys encrypted per-user in database

### File Integrity
- `.docx` placeholders replaced safely without corruption
- Original files retained for audit and re-generation
- PDF generation validates before serving
- Temporary files cleaned on Vercel (ephemeral filesystem)

---

## 🤖 AI-Powered Document Generation

The system can auto-compose Arabic documents using your LLM of choice:

### Supported Models
1. **Google Gemini** (recommended for Arabic)
2. **Groq** (fast, multi-language)
3. **OpenAI** (GPT-4 compatible)

### Configuration
1. Go to **Settings** → **API Keys**
2. Paste your API key for desired provider
3. Keys are encrypted and stored per-user
4. Models available during document composition

### Usage
1. Click **"AI Compose"** on dashboard
2. Select document type: Letter or Request
3. Fill in metadata (sender, recipient, subject, etc.)
4. Provide a draft outline
5. AI auto-completes the formal Arabic content
6. Review and finalize
7. System generates .docx with placeholders replaced

---

## 💾 Database Models

### Document
```python
id                    # Primary key
serial_number         # Sequential number within month
full_code             # Formatted code (e.g., "0042 ESSIC 07-2026")
month, year           # For monthly reset logic
filename              # Original uploaded filename
file_title            # User-provided title
generated_filename    # Output .docx name
generated_pdf_filename # Output .pdf name (if generated)
doc_type              # "upload" or "direct" or "ai"
status                # "pending", "approved", "rejected"
username              # User's display name
email                 # User's email
created_at, updated_at # Timestamps
# AI-specific fields:
ai_model              # "gemini", "groq", "deepseek"
sender, recipient, subject, holder_name, position, generated_body
```

### User
```python
id                    # Primary key
email                 # Unique identifier
name                  # Display name
totp_secret           # Base32-encoded secret for 2FA
is_setup              # Whether user completed 2FA setup
role                  # "admin" or "user"
gemini_api_key        # Encrypted Gemini API key (user)
groq_api_key          # Encrypted Groq API key (user)
deepseek_api_key      # Encrypted DeepSeek API key (user)
created_at, updated_at # Timestamps
```

---

## 🚢 Deployment

### Vercel (Current Production)

**Live Instance:** [https://essic-3fty.vercel.app/](https://essic-3fty.vercel.app/)

1. **Connect Repository**: Link GitHub repo to Vercel
2. **Set Environment Variables** in Vercel dashboard:
   - `SUPABASE_DB_URL`
   - `ADMIN_EMAILS`
   - `ALLOWED_EMAILS`
   - `ONEDRIVE_SHARE_URL` (optional)
   - `VERCEL=1`

3. **Deploy**:
   ```bash
   vercel deploy --prod
   ```

4. **File Storage**: Uses `/tmp` (ephemeral — files deleted after request)
   - Optional: Configure persistent storage via Vercel Blob Storage

### Local Deployment (Docker)

1. **Build Docker image**:
   ```bash
   docker build -t essic:latest .
   ```

2. **Run container**:
   ```bash
   docker run -e SUPABASE_DB_URL='...' \
              -e ADMIN_EMAILS='...' \
              -e ALLOWED_EMAILS='...' \
              -p 5010:5010 essic:latest
   ```

### Self-Hosted (Linux/Ubuntu)

1. **Install system dependencies**:
   ```bash
   sudo apt update
   sudo apt install python3.10 python3-pip python3-venv
   sudo apt install libpq-dev  # For PostgreSQL support
   ```

2. **Clone & setup**:
   ```bash
   git clone https://github.com/elshafee/ESSIC.git
   cd ESSIC/flask
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Configure Gunicorn** (production server):
   ```bash
   pip install gunicorn
   gunicorn -w 4 -b 0.0.0.0:5010 app:app
   ```

4. **Use Nginx** as reverse proxy:
   ```nginx
   server {
       listen 80;
       server_name essic.example.com;
   
       location / {
           proxy_pass http://127.0.0.1:5010;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
       }
   }
   ```

---

## 🧪 Testing

### Manual Testing Checklist

- [ ] Login with valid email → 2FA setup required
- [ ] Upload .docx template → Code inserted correctly
- [ ] Generate PDF → Document displays formatted
- [ ] Edit serial number → No duplicates allowed
- [ ] Delete document → Files removed from disk
- [ ] Admin approval → OneDrive upload triggered
- [ ] AI composition → Arabic text generated & formatted
- [ ] User role changes → Permissions update immediately
- [ ] Session timeout → Redirect to login after inactivity

### Automated Testing (Future)
```bash
pytest tests/
```

---

## 📝 Template Requirements

For custom .docx templates, use these exact placeholders:

| Placeholder | Purpose | Example |
|-------------|---------|---------|
| `{{CODE_NUMBER}}` | Document code | `0042 ESSIC 07-2026` |
| `{{SEND_TO}}` | Recipient office (Arabic) | `مكتب العميد` |
| `{{SUBJECT}}` | Subject line (Arabic) | `طلب موافقة على مشروع` |
| `{{STACK_HOLDER}}` | Holder's name (Arabic) | `السيد الأستاذ الدكتور / محمد` |
| `{{POSITION}}` | Position title (Arabic) | `نائب رئيس الجامعة` |
| `{{BODY_TEXT}}` | Document body (Arabic) | Multi-paragraph letter content |
| `{{SENDER}}` | Sender name (optional) | Employee or manager signature |
| `{{ESSIC}}` | Organization identifier | `ESSIC` (or blank) |

**Important:** 
- Placeholders can appear anywhere in document (paragraphs, tables, headers, footers)
- Text formatting (font, size, color, bold, italic) is preserved during replacement
- Arabic text direction and bidirectional markers (`\u202A`, `\u202B`, `\u202C`) are auto-applied
- Logos and images remain untouched

---

## 🐛 Troubleshooting

### Common Issues

#### Database Connection Error
**Error:** `SUPABASE_DB_URL environment variable is required and not set.`

**Solution:**
```bash
# Add to .env file:
SUPABASE_DB_URL=postgresql+psycopg://user:pass@host/dbname
```

#### File Not Found After Upload
**Cause:** Vercel uses ephemeral filesystem; files deleted between requests

**Solution:** Configure persistent storage or use OneDrive integration

#### PDF Generation Fails
**Cause:** `libreoffice` not installed (for docx2pdf)

**Solution:**
```bash
# Ubuntu/Debian:
sudo apt install libreoffice-writer

# Alternatively, disable PDF generation (graceful fallback)
```

#### TOTP Setup Not Visible
**Cause:** Browser blocking QR code display

**Solution:** Use manual entry instead of QR code

#### Admin Functions Not Accessible
**Cause:** User's email not in `ADMIN_EMAILS`

**Solution:** Update `.env` and restart application

---

## 📊 Performance Considerations

- **Database Indexing**: Indexed on `email`, `month`, `year` for fast lookups
- **File Storage**: Local/temporary for Vercel, persistent for OneDrive
- **Concurrent Users**: PostgreSQL supports multiple connections; scale via connection pool
- **PDF Generation**: CPU-intensive; consider async queuing for high volume

### Optimization Tips
1. Use PostgreSQL connection pooling (pgBouncer)
2. Cache AI model responses for identical inputs
3. Compress PDFs before OneDrive upload
4. Batch user exports during off-peak hours

---

## 🤝 Contributing

Contributions are welcome! Please follow these steps:

1. **Fork the repository**
2. **Create a feature branch**: `git checkout -b feature/your-feature`
3. **Commit changes**: `git commit -m "Add your feature"`
4. **Push to branch**: `git push origin feature/your-feature`
5. **Open a Pull Request** with detailed description

### Code Style
- Follow PEP 8 for Python
- Use type hints where applicable
- Add docstrings for all functions
- Test locally before submitting PR

---

## 📄 License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

---

## 👨‍💼 Author & Support

**Developed by:** [Ahmed Elshafee](https://github.com/elshafee)

**Live Demo:** [https://essic-3fty.vercel.app/](https://essic-3fty.vercel.app/)

**Report Issues:** [GitHub Issues](https://github.com/elshafee/ESSIC/issues)

---

## 🙏 Acknowledgments

- Built with [Flask](https://flask.palletsprojects.com/) and [SQLAlchemy](https://www.sqlalchemy.org/)
- AI integration via [Google Generative AI](https://ai.google.dev/), [Groq](https://groq.com/), [OpenAI](https://openai.com/)
- Document processing with [python-docx](https://python-docx.readthedocs.io/)
- Deployed on [Vercel](https://vercel.com/) with [Supabase PostgreSQL](https://supabase.com/)

---

## 📌 Changelog

### v1.0.0 (Current)
- ✅ Document numbering system
- ✅ .docx template processing
- ✅ TOTP 2FA authentication
- ✅ Role-based access control
- ✅ OneDrive integration
- ✅ AI document composition (Gemini, Groq, DeepSeek)
- ✅ PDF generation
- ✅ Vercel deployment

### Planned Features
- [ ] Document approval workflows
- [ ] Email notifications
- [ ] Advanced search & filtering
- [ ] Batch document generation
- [ ] REST API for third-party integration
- [ ] Multi-language support

---

## 📞 Contact & Support

For questions, feature requests, or bug reports, please open an [issue on GitHub](https://github.com/elshafee/ESSIC/issues) or contact the maintainer.

**Visit the live application:** [https://essic-3fty.vercel.app/](https://essic-3fty.vercel.app/)
