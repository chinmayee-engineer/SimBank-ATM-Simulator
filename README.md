🏦 SimBank ATM Simulator System
> **A professional, fully offline ATM simulation platform built with Python and PySide6, featuring a standalone debit-card generator and a realistic desktop ATM simulator.**
Designed & Developed by Chinmayee
![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)
![PySide6](https://img.shields.io/badge/PySide6-GUI-41CD52?style=for-the-badge&logo=qt&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-Local%20Storage-003B57?style=for-the-badge&logo=sqlite&logoColor=white)
![Excel](https://img.shields.io/badge/Excel-XLSX-217346?style=for-the-badge&logo=microsoftexcel&logoColor=white)
![PDF](https://img.shields.io/badge/PDF-Receipts-B30B00?style=for-the-badge&logo=adobeacrobatreader&logoColor=white)
![Offline](https://img.shields.io/badge/Mode-100%25%20Offline-2E7D32?style=for-the-badge)
---
📌 Overview
SimBank ATM Simulator System is a desktop-based educational and demonstration project designed to reproduce the workflow of a modern ATM environment without connecting to any real banking network.
The system consists of two independent PySide6 applications:
Card Generator — creates and manages fictional debit cards, accounts, PINs, balances, limits, and card states.
ATM Simulator — authenticates generated cards and provides a realistic ATM transaction experience.
Both applications communicate through a shared local SQLite database, allowing the card generator and ATM simulator to operate together while remaining completely offline.
> ⚠️ **Simulation / Test Only:** This project does not connect to real banks, payment networks, financial institutions, or real-money accounts. All cards, accounts, balances, transactions, and ATM cash values are fictional.
---
✨ Key Highlights
🖥️ Professional desktop GUI built with PySide6
💳 Fictional debit-card generation and lifecycle management
🔐 Secure salted PBKDF2-SHA256 PIN hashing
🔢 Luhn-valid simulated card numbers
🏧 Multiple simulated ATM locations
💰 Realistic denomination-based cash dispensing
💵 Cash deposit simulation
📊 Balance inquiry and transaction statements
🔄 Account-to-account fund transfers
🔒 PIN change and three-attempt security lockout
🧾 PDF receipt generation
📑 Excel statement export
👨‍💼 Password-protected administration dashboard
🛠️ ATM failure and fault simulation
🌐 Multi-language customer interface
📝 Security and transaction event logging
💾 Fully local/offline data storage
📦 Windows executable packaging support
---
🧩 System Architecture
```text
                 ┌─────────────────────────┐
                 │     CARD GENERATOR      │
                 │                         │
                 │ • Create Cards          │
                 │ • Manage Accounts       │
                 │ • Manage PINs           │
                 │ • Card Lifecycle        │
                 │ • Search / Filter       │
                 └────────────┬────────────┘
                              │
                              │ Shared Local Database
                              ▼
                 ┌─────────────────────────┐
                 │      SQLite DB          │
                 │                         │
                 │ • Cards                 │
                 │ • Accounts              │
                 │ • Transactions          │
                 │ • ATM State             │
                 │ • Security Events       │
                 │ • Failure Flags         │
                 └────────────┬────────────┘
                              │
                              ▼
                 ┌─────────────────────────┐
                 │      ATM SIMULATOR      │
                 │                         │
                 │ • Card Authentication  │
                 │ • Withdraw / Deposit   │
                 │ • Balance / Statements │
                 │ • Transfers            │
                 │ • PIN Management        │
                 │ • Admin Dashboard       │
                 └─────────────────────────┘
```
---
🚀 Features
💳 1. Debit Card Generator
The Card Generator application provides a complete fictional card-issuance workflow.
Card creation
Generate individual cards
Bulk-generate up to 500 cards
Custom or randomly generated customer names
Opening balance configuration
Daily withdrawal limits
Daily transfer limits
Custom or randomly generated 4-digit PIN
Configurable validity period
Generated card information
Each simulated card receives:
Fictional 16-digit card number
Luhn-valid card number
Account number
CVV
Cardholder name
Expiry date
Account balance
Transaction limits
Securely hashed PIN
The system does not store the original PIN as plain text.
Card lifecycle management
Administrators can:
Activate cards
Deactivate cards
Lock cards
Unlock cards
Retain cards
Change PIN
Reset PIN
Delete cards
View complete card information
Card directory
Cards can be searched and filtered using:
Customer name
Card number
Account number
Card status
The application also includes a visual card preview with a permanent simulation watermark.
---
🏧 2. ATM Simulator
The ATM application reproduces a realistic customer transaction workflow.
🔐 Card Authentication
The ATM supports:
Card number authentication
PIN verification
Three-attempt PIN protection
Automatic card retention after the third failed attempt
Invalid/locked/inactive/retained card handling
Session-based authentication
This allows the card generated by the Card Generator to be authenticated directly by the simulated ATM.
---
💰 3. Balance Inquiry
Customers can view their current simulated account balance directly from the ATM interface.
---
💵 4. Cash Withdrawal
The withdrawal system supports:
Quick withdrawal amounts
Custom withdrawal amounts
Daily withdrawal limits
ATM cash availability checks
Denomination-aware cash dispensing
ATM-specific cash inventory
Low-cash warnings
Out-of-cash handling
Transaction IDs
Receipt generation
Supported simulated denominations:
```text
₹2000
₹500
₹200
₹100
₹50
```
The ATM only completes a withdrawal when the requested amount can be satisfied by its available denomination inventory.
---
💴 5. Cash Deposit
The simulated ATM supports denomination-based cash deposits.
Customers can enter notes by denomination and the system updates:
Account balance
ATM cash inventory
Transaction history
---
📋 6. Mini Statement
Customers can view recent account transactions directly through the ATM.
---
📊 7. Full Statement
The statement system provides advanced filtering options including:
Transaction type
Transaction status
Date range
Free-text search
Transaction ID
Statements can also be exported to Excel (.xlsx).
---
🔎 8. Transaction Search
Transactions can be searched using available transaction information, allowing users to quickly locate specific activity.
Every transaction receives a unique transaction ID.
---
🔄 9. Fund Transfer
The system supports simulated account-to-account transfers.
Transfer processing includes:
Source account validation
Destination account validation
Balance validation
Daily transfer limits
Transaction recording
Unique transaction ID
Failure handling
No real money or banking network is involved.
---
🔐 10. PIN Management
Customers can change their PIN through the ATM.
The project uses salted PBKDF2-SHA256 hashing for PIN verification instead of storing the PIN directly.
The ATM also implements a strict three-attempt protection mechanism.
---
📕 11. Cheque Book Request
Customers can submit a simulated cheque-book request through the ATM interface.
---
🧾 12. Receipt System
Transactions can generate receipts that can be:
Saved as PDF
Sent to a simulated print workflow
Receipt generation is integrated with transaction processing so customers can retain a record of their activity.
---
📑 13. Excel Export
Full transaction statements can be exported to:
```text
.xlsx
```
The export functionality is implemented using openpyxl.
---
👨‍💼 14. Admin Dashboard
The system includes a password-protected administration interface.
Administrators can manage:
Card & customer management
View cards
Search cards
Change card status
Manage customer/card records
ATM management
View ATM status
Manage ATM cash
Refill cash
Inspect denomination inventory
Security monitoring
View security events
Review failed authentication activity
Inspect system events
System diagnostics
Inspect simulated system conditions
Review ATM state
Manage failure scenarios
---
🛠️ 15. Failure Simulation
A major feature of this project is the ability to simulate ATM hardware and system failures.
The Admin Dashboard provides controls for:
```text
Card Reader Failure
Cash Dispenser Failure
Receipt Printer Failure
Network Unavailable
Low Cash Warning
Out of Cash
Database Unavailable
Force Invalid Card
Force Card Retained
Transaction Timeout
```
These failures are simulation controls only.
Transaction safety
A failed transaction must not partially modify account balances.
The system validates required conditions before committing money movement, helping demonstrate how transactional ATM workflows should behave under fault conditions.
---
🌐 16. Multi-Language Support
The customer-facing ATM interface includes:
🇬🇧 English
🇮🇳 Hindi
Kannada
Tamil
Telugu
Malayalam
Marathi
Bengali
Gujarati
Punjabi
Language selection is handled through the shared internationalization module.
---
🗂️ Project Structure
```text
ATM_SYSTEM/
│
├── shared/
│   ├── db.py
│   ├── security.py
│   ├── i18n.py
│   ├── theme.py
│   ├── documents.py
│   └── __init__.py
│
├── card_generator/
│   ├── main.py
│   ├── app.py
│   ├── widgets.py
│   └── __init__.py
│
├── atm_simulator/
│   ├── main.py
│   ├── app.py
│   ├── session.py
│   ├── keypad.py
│   ├── admin.py
│   └── __init__.py
│
├── data/
│   └── .gitkeep
│
├── receipts/
│   └── .gitkeep
│
├── exports/
│   └── .gitkeep
│
├── requirements.txt
└── README.md
```
---
⚙️ Technology Stack
Technology	Purpose
Python	Core application logic
PySide6	Desktop GUI
SQLite	Local database
openpyxl	Excel export
ReportLab	PDF receipt generation
PBKDF2-SHA256	Secure PIN hashing
PyInstaller	Windows executable packaging
---
💾 Data Storage
The project is intentionally designed to work without any external database server.
All application data is stored locally using SQLite.
Typical runtime storage:
```text
data/
└── atm_system.db

receipts/
└── *.pdf

exports/
└── *.xlsx
```
No cloud database or external banking service is required.
> **Important:** Runtime-generated database files, receipts, and exports should generally not be committed to GitHub.
---
🛠️ Installation
1. Clone the repository
```bash
git clone https://github.com/YOUR_USERNAME/YOUR_REPOSITORY.git
cd YOUR_REPOSITORY
```
2. Create a virtual environment
Windows
```bash
python -m venv venv
venv\Scripts\activate
```
macOS / Linux
```bash
python3 -m venv venv
source venv/bin/activate
```
3. Install dependencies
```bash
pip install -r requirements.txt
```
---
▶️ Running the Applications
Start the Card Generator
From the project root:
```bash
python -m card_generator.main
```
Create one or more fictional cards before using the ATM.
Start the ATM Simulator
```bash
python -m atm_simulator.main
```
The ATM simulator will use the same local database created by the Card Generator.
---
🔑 Default Admin Access
The default simulated administrator password is:
```text
admin123
```
> This password exists only for demonstration purposes. It should be changed before distributing the application.
---
📦 Build Windows Executables
Install PyInstaller:
```bash
pip install pyinstaller
```
Build the Card Generator:
```bash
pyinstaller --noconfirm --windowed --name "SimBank-CardGenerator" --paths . card_generator/main.py
```
Build the ATM Simulator:
```bash
pyinstaller --noconfirm --windowed --name "SimBank-ATM" --paths . atm_simulator/main.py
```
The generated applications will be placed under:
```text
dist/
├── SimBank-CardGenerator/
└── SimBank-ATM/
```
For this architecture, the `--onedir` approach is recommended so persistent SQLite data can remain outside the temporary extraction directory used by one-file applications.
---
🔗 Shared Data Directory
When the applications are packaged separately, both applications can be configured to use the same persistent data directory through:
```text
ATM_SIM_DATA_DIR
```
Example on Windows:
```bat
set ATM_SIM_DATA_DIR=C:\SimBank\shared_data
```
Then launch either executable from the same configured environment.
---
🧪 Testing & Reliability
The project is designed as a functional ATM simulation rather than a static UI mockup.
Important workflows include:
Card creation
Card authentication
PIN verification
PIN lockout
Card retention
Balance inquiry
Withdrawals
Deposits
Transfers
Daily limits
Statement generation
PDF receipts
Excel exports
PIN changes
ATM cash management
Failure simulation
Administrative operations
The failure-simulation design also emphasizes transaction integrity: simulated failures should not result in unintended balance changes.
---
🔒 Security Notes
This is an educational simulation, not production banking software.
Security-related implementation concepts demonstrated by the project include:
Salted PBKDF2-SHA256 PIN hashing
PIN verification
Failed-attempt tracking
Card status controls
Transaction identifiers
Administrative authentication
Security event logging
Local-only data processing
The system should never be used to process real financial information or real payment-card credentials.
---
⚠️ Disclaimer
SimBank ATM Simulator System is a fictional educational software project.
It is not affiliated with, sponsored by, or connected to any real bank, payment network, card issuer, financial institution, ATM manufacturer, or financial service.
All:
Card numbers
Account numbers
PINs
CVVs
Balances
Transactions
ATM cash
Customer information
are simulated and intended solely for development, testing, learning, and demonstration.
---
🎯 Learning Objectives
This project demonstrates practical software-development concepts including:
Desktop GUI development
Object-oriented Python
Database-backed applications
Secure credential handling
Transaction processing
State management
Validation
Error handling
File generation
Excel automation
PDF generation
Internationalization
Administrative dashboards
Hardware/failure simulation
Application packaging
---
🚀 Future Enhancements
Possible future improvements include:
🔐 Two-factor authentication for administrators
📱 QR-based simulated card authentication
📈 Advanced analytics dashboard
🧑‍💼 Role-based administrator accounts
🏧 More ATM hardware simulations
📊 Visual transaction analytics
🗃️ Automated database backup and restore
🧪 Dedicated automated test suite
🌙 Additional UI themes
📦 Installer-based Windows distribution
---
👩‍💻 Author
Designed & Developed by Chinmayee
Built as a professional Python desktop application project focused on ATM workflow simulation, secure local data handling, GUI development, and realistic transaction processing.
---
⭐ Support
If you find this project useful for learning, experimentation, or demonstration:
⭐ Star the repository
🍴 Fork the project
🐛 Report issues
💡 Suggest improvements
🔧 Submit pull requests
---
📄 License
Add your preferred open-source license before publishing, such as MIT, Apache-2.0, or another license appropriate for your project.
---
SimBank ATM Simulator System — A realistic offline ATM simulation for development, education, and demonstration.
