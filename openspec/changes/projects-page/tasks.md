## Tasks

### Task 1: Add /projects route to dashboard.py
- New route serving `projects.html` template
- Query all projects with receipt_count and total_spend (same query as settings page)
- Pass projects list to template

### Task 2: Create projects.html template
- Extends base.html, sets active_page = "projects"
- Page header with "+ Add Project" button
- Hidden add form: name, code, address, city, state, start date, end date, notes
- Search bar (filter by name/code/city)
- Table: Name, Code, Location, Status badge, Start Date, Receipts, Spend, Actions (Edit, status toggle, Remove)
- Inline edit form (appears below row on Edit click)
- JavaScript: add, edit, status toggle, remove, search filter

### Task 3: Update base.html nav
- Add "Projects" link between "Employees" and Settings gear
- Highlight when active_page == "projects"

### Task 4: Simplify settings.html
- Remove entire projects section (form + table + JS)
- Add "Project Management" link card (matching Employee Management card style)
- Remove projects-related JavaScript functions
- Settings route no longer needs to query projects (only for email filter dropdown)
