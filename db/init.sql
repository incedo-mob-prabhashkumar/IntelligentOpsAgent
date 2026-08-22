CREATE TABLE IF NOT EXISTS employees (
    employee_id VARCHAR(16) PRIMARY KEY,
    name TEXT NOT NULL,
    department TEXT NOT NULL,
    email TEXT NOT NULL,
    location TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS knowledge_base (
    article_id VARCHAR(16) PRIMARY KEY,
    title TEXT NOT NULL,
    tags TEXT[] NOT NULL DEFAULT '{}',
    content TEXT NOT NULL,
    last_updated DATE NOT NULL
);

CREATE TABLE IF NOT EXISTS tickets (
    ticket_id VARCHAR(16) PRIMARY KEY,
    employee_id VARCHAR(16) NOT NULL REFERENCES employees(employee_id),
    summary TEXT NOT NULL,
    category TEXT NOT NULL,
    priority TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    notes TEXT[] NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_tickets_employee ON tickets (employee_id);
CREATE INDEX IF NOT EXISTS idx_tickets_status ON tickets (status);

INSERT INTO employees (employee_id, name, department, email, location)
VALUES
    ('EMP1024', 'Aarav Mehta', 'Finance', 'aarav.mehta@example.com', 'Bengaluru'),
    ('EMP2048', 'Diya Nair', 'Engineering', 'diya.nair@example.com', 'Pune'),
    ('EMP3001', 'Rohan Iyer', 'Sales', 'rohan.iyer@example.com', 'Mumbai')
ON CONFLICT (employee_id) DO NOTHING;

INSERT INTO knowledge_base (article_id, title, tags, content, last_updated)
VALUES
    ('KB-001', 'Reset VPN Password', ARRAY['vpn','password','reset','remote-access'], 'Open the Self-Service Portal, choose ''Reset Network Password'', complete MFA, and wait 2 minutes before reconnecting VPN.', '2026-05-10'),
    ('KB-002', 'Fix Outlook Not Syncing', ARRAY['email','outlook','sync'], 'Check internet connectivity, restart Outlook, then recreate your profile from Control Panel > Mail if sync issues continue.', '2026-04-22'),
    ('KB-003', 'Laptop Battery Health Check', ARRAY['laptop','battery','hardware'], 'Run the vendor diagnostics app and submit the generated battery report to IT support if health is below 60%.', '2026-06-15'),
    ('KB-004', 'Corporate Wi-Fi Troubleshooting', ARRAY['wifi','network','connectivity'], 'Forget the corporate SSID, reconnect using your company credentials, and verify your device time is set automatically.', '2026-07-01')
ON CONFLICT (article_id) DO NOTHING;

INSERT INTO tickets (ticket_id, employee_id, summary, category, priority, status, created_at, updated_at, notes)
VALUES
    ('TKT1001', 'EMP1024', 'VPN disconnects every 10 minutes', 'network', 'high', 'in_progress', '2026-08-15T09:30:00Z', '2026-08-20T11:10:00Z', ARRAY['Initial diagnostics completed','Awaiting user logs']),
    ('TKT1002', 'EMP2048', 'Outlook mailbox not syncing', 'software', 'medium', 'open', '2026-08-18T12:05:00Z', '2026-08-18T12:05:00Z', ARRAY['Assigned to messaging support queue'])
ON CONFLICT (ticket_id) DO NOTHING;
