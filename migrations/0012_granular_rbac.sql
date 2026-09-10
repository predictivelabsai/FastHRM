-- Per-role module permissions. Missing rows intentionally preserve the
-- pre-RBAC behaviour for staff accounts.
CREATE TABLE IF NOT EXISTS role_permissions (
    id         INTEGER PRIMARY KEY,
    role_name  TEXT NOT NULL,
    module_key TEXT NOT NULL CHECK (module_key IN (
        'dashboard', 'ai', 'employee-portal', 'employees', 'departments',
        'leave', 'attendance', 'shifts', 'timeclock', 'payroll', 'expenses',
        'travel', 'platform', 'jobs', 'candidates', 'offers',
        'talent-analytics', 'goals', 'feedback', 'reviews', 'signals',
        'onboarding', 'changes', 'separations', 'cases', 'org',
        'integrations', 'prompts', 'roles', 'guide', 'developers'
    )),
    can_view  INTEGER NOT NULL DEFAULT 0 CHECK (can_view IN (0, 1)),
    can_edit  INTEGER NOT NULL DEFAULT 0 CHECK (can_edit IN (0, 1)),
    UNIQUE(role_name, module_key)
);

CREATE INDEX IF NOT EXISTS idx_role_permissions_role
    ON role_permissions(role_name);

-- Administrators retain full access. HRBP and recruiter rows capture the
-- coarse role boundaries already described by the Roles & access screen.
INSERT INTO role_permissions(role_name, module_key, can_view, can_edit)
WITH modules(key) AS (VALUES
    ('dashboard'), ('ai'), ('employee-portal'), ('employees'), ('departments'),
    ('leave'), ('attendance'), ('shifts'), ('timeclock'), ('payroll'),
    ('expenses'), ('travel'), ('platform'), ('jobs'), ('candidates'), ('offers'),
    ('talent-analytics'), ('goals'), ('feedback'), ('reviews'), ('signals'),
    ('onboarding'), ('changes'), ('separations'), ('cases'), ('org'),
    ('integrations'), ('prompts'), ('roles'), ('guide'), ('developers'))
SELECT 'admin', key, 1, 1 FROM modules
WHERE NOT EXISTS (
    SELECT 1 FROM role_permissions p
    WHERE p.role_name = 'admin' AND p.module_key = modules.key
);

INSERT INTO role_permissions(role_name, module_key, can_view, can_edit)
WITH roles(role_name) AS (VALUES ('hrbp'), ('recruiter')),
modules(key) AS (VALUES
    ('dashboard'), ('ai'), ('employee-portal'), ('employees'), ('departments'),
    ('leave'), ('attendance'), ('shifts'), ('timeclock'), ('payroll'), ('expenses'),
    ('travel'), ('platform'), ('jobs'), ('candidates'), ('offers'),
    ('talent-analytics'), ('goals'), ('feedback'), ('reviews'), ('signals'),
    ('onboarding'), ('changes'), ('separations'), ('cases'), ('org'),
    ('integrations'), ('prompts'), ('roles'), ('guide'), ('developers'))
SELECT roles.role_name, modules.key,
       CASE WHEN roles.role_name = 'hrbp' AND modules.key IN (
           'dashboard', 'ai', 'employees', 'departments', 'leave', 'attendance',
           'shifts', 'timeclock', 'payroll', 'expenses', 'travel', 'goals',
           'feedback', 'reviews', 'signals', 'onboarding', 'changes',
           'separations', 'cases', 'org') THEN 1
            WHEN roles.role_name = 'recruiter' AND modules.key IN (
           'dashboard', 'ai', 'platform', 'jobs', 'candidates', 'offers',
           'talent-analytics', 'prompts') THEN 1 ELSE 0 END,
       CASE WHEN roles.role_name = 'hrbp' AND modules.key IN (
           'dashboard', 'ai', 'employees', 'departments', 'leave', 'attendance',
           'shifts', 'timeclock', 'payroll', 'expenses', 'travel', 'goals',
           'feedback', 'reviews', 'signals', 'onboarding', 'changes',
           'separations', 'cases', 'org') THEN 1
            WHEN roles.role_name = 'recruiter' AND modules.key IN (
           'dashboard', 'ai', 'platform', 'jobs', 'candidates', 'offers',
           'talent-analytics', 'prompts') THEN 1 ELSE 0 END
FROM roles CROSS JOIN modules
WHERE NOT EXISTS (
    SELECT 1 FROM role_permissions p
    WHERE p.role_name = roles.role_name AND p.module_key = modules.key
);
