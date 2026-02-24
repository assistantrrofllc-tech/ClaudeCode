## 1. API Endpoints

- [ ] 1.1 Create GET `/api/crew/employees/<id>/certs` — full cert list for one employee
- [ ] 1.2 Create POST `/api/crew/certifications` — add a new certification
- [ ] 1.3 Create PUT `/api/crew/certifications/<id>` — edit a certification
- [ ] 1.4 Create POST `/api/crew/certifications/<id>/delete` — soft-delete a certification

## 2. Detail Page Template

- [ ] 2.1 Create `crew_detail.html` extending base with tab bar
- [ ] 2.2 Identity card section (name, phone, email, crew, role, status, avatar placeholder)
- [ ] 2.3 Edit employee inline form (toggle editable fields + save)
- [ ] 2.4 Cert badge row with scroll-to-table anchors
- [ ] 2.5 Certifications table (type, issued, expires, status pill, document placeholder, actions)
- [ ] 2.6 Add Certification modal/form
- [ ] 2.7 Edit/delete cert actions
- [ ] 2.8 Notes section with save button
- [ ] 2.9 Safety violations placeholder (empty state)

## 3. Route & Navigation

- [ ] 3.1 Add `/crew/<int:employee_id>` route in dashboard.py
- [ ] 3.2 Pass employee data, cert types, and certs to template

## 4. CSS

- [ ] 4.1 Identity card styles
- [ ] 4.2 Cert table status pill styles
- [ ] 4.3 Detail page responsive layout

## 5. Testing

- [ ] 5.1 Test cert CRUD API endpoints
- [ ] 5.2 Test detail page renders for valid employee
- [ ] 5.3 Test 404 for invalid employee
- [ ] 5.4 Run full test suite
