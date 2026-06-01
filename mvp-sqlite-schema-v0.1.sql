PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS project_statuses (
  code TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  sort_order INTEGER NOT NULL,
  is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1))
);

CREATE TABLE IF NOT EXISTS file_categories (
  code TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  default_folder TEXT NOT NULL,
  sort_order INTEGER NOT NULL,
  is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1))
);

CREATE TABLE IF NOT EXISTS todo_types (
  code TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  sort_order INTEGER NOT NULL,
  is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1))
);

CREATE TABLE IF NOT EXISTS customers (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL COLLATE NOCASE UNIQUE,
  short_name TEXT,
  country_region TEXT,
  industry TEXT,
  notes TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS contacts (
  id TEXT PRIMARY KEY,
  customer_id TEXT NOT NULL,
  name TEXT NOT NULL,
  role TEXT,
  phone TEXT,
  email TEXT,
  wechat TEXT,
  is_primary INTEGER NOT NULL DEFAULT 0 CHECK (is_primary IN (0, 1)),
  notes TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (customer_id) REFERENCES customers(id) ON UPDATE CASCADE ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS projects (
  id TEXT PRIMARY KEY,
  equipment_no TEXT NOT NULL COLLATE NOCASE UNIQUE,
  source_type TEXT NOT NULL CHECK (source_type IN ('new', 'historical_manual', 'historical_scan_pending')),
  customer_id TEXT NOT NULL,
  contact_id TEXT,
  project_name TEXT,
  equipment_name TEXT,
  status_code TEXT NOT NULL,
  currency TEXT NOT NULL DEFAULT 'CNY',
  estimated_quote_amount NUMERIC CHECK (estimated_quote_amount IS NULL OR estimated_quote_amount >= 0),
  final_quote_amount NUMERIC CHECK (final_quote_amount IS NULL OR final_quote_amount >= 0),
  po_amount NUMERIC CHECK (po_amount IS NULL OR po_amount >= 0),
  inquiry_date TEXT,
  quote_date TEXT,
  po_date TEXT,
  expected_delivery_date TEXT,
  actual_ship_date TEXT,
  project_folder_path TEXT,
  original_source_path TEXT,
  has_quote INTEGER NOT NULL DEFAULT 0 CHECK (has_quote IN (0, 1)),
  has_po INTEGER NOT NULL DEFAULT 0 CHECK (has_po IN (0, 1)),
  has_3d_model INTEGER NOT NULL DEFAULT 0 CHECK (has_3d_model IN (0, 1)),
  is_historical INTEGER NOT NULL DEFAULT 0 CHECK (is_historical IN (0, 1)),
  is_data_complete INTEGER NOT NULL DEFAULT 0 CHECK (is_data_complete IN (0, 1)),
  is_archived INTEGER NOT NULL DEFAULT 0 CHECK (is_archived IN (0, 1)),
  notes TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (customer_id) REFERENCES customers(id) ON UPDATE CASCADE ON DELETE RESTRICT,
  FOREIGN KEY (contact_id) REFERENCES contacts(id) ON UPDATE CASCADE ON DELETE SET NULL,
  FOREIGN KEY (status_code) REFERENCES project_statuses(code) ON UPDATE CASCADE ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS project_files (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  original_name TEXT NOT NULL,
  current_name TEXT NOT NULL,
  extension TEXT,
  category_code TEXT NOT NULL,
  file_path TEXT NOT NULL,
  original_source_path TEXT,
  size_bytes INTEGER CHECK (size_bytes IS NULL OR size_bytes >= 0),
  modified_at TEXT,
  is_3d_model INTEGER NOT NULL DEFAULT 0 CHECK (is_3d_model IN (0, 1)),
  text_extracted INTEGER NOT NULL DEFAULT 0 CHECK (text_extracted IN (0, 1)),
  extracted_text TEXT,
  content_hash TEXT,
  import_method TEXT NOT NULL CHECK (import_method IN ('new_project_copy', 'historical_link', 'historical_copy', 'scan_pending')),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (project_id) REFERENCES projects(id) ON UPDATE CASCADE ON DELETE CASCADE,
  FOREIGN KEY (category_code) REFERENCES file_categories(code) ON UPDATE CASCADE ON DELETE RESTRICT,
  UNIQUE (project_id, file_path)
);

CREATE TABLE IF NOT EXISTS quotes (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  version_label TEXT,
  quote_date TEXT,
  amount NUMERIC CHECK (amount IS NULL OR amount >= 0),
  currency TEXT NOT NULL DEFAULT 'CNY',
  file_id TEXT,
  is_final INTEGER NOT NULL DEFAULT 0 CHECK (is_final IN (0, 1)),
  notes TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (project_id) REFERENCES projects(id) ON UPDATE CASCADE ON DELETE CASCADE,
  FOREIGN KEY (file_id) REFERENCES project_files(id) ON UPDATE CASCADE ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS purchase_orders (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  po_no TEXT,
  po_date TEXT,
  amount NUMERIC CHECK (amount IS NULL OR amount >= 0),
  currency TEXT NOT NULL DEFAULT 'CNY',
  file_id TEXT,
  is_partial INTEGER NOT NULL DEFAULT 0 CHECK (is_partial IN (0, 1)),
  notes TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (project_id) REFERENCES projects(id) ON UPDATE CASCADE ON DELETE CASCADE,
  FOREIGN KEY (file_id) REFERENCES project_files(id) ON UPDATE CASCADE ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS todos (
  id TEXT PRIMARY KEY,
  project_id TEXT,
  type_code TEXT NOT NULL,
  title TEXT NOT NULL,
  due_date TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'completed', 'cancelled')),
  completed_at TEXT,
  notes TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (project_id) REFERENCES projects(id) ON UPDATE CASCADE ON DELETE CASCADE,
  FOREIGN KEY (type_code) REFERENCES todo_types(code) ON UPDATE CASCADE ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS project_events (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  event_type TEXT NOT NULL,
  title TEXT NOT NULL,
  detail TEXT,
  created_at TEXT NOT NULL,
  FOREIGN KEY (project_id) REFERENCES projects(id) ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS backup_records (
  id TEXT PRIMARY KEY,
  backup_type TEXT NOT NULL CHECK (backup_type IN ('database', 'index', 'config', 'full')),
  backup_path TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('success', 'failed')),
  message TEXT,
  created_at TEXT NOT NULL
);

CREATE VIRTUAL TABLE IF NOT EXISTS file_search
USING fts5(
  file_id UNINDEXED,
  project_id UNINDEXED,
  file_name,
  extracted_text,
  tokenize = 'unicode61'
);

CREATE INDEX IF NOT EXISTS idx_contacts_customer_id ON contacts(customer_id);
CREATE INDEX IF NOT EXISTS idx_projects_customer_id ON projects(customer_id);
CREATE INDEX IF NOT EXISTS idx_projects_contact_id ON projects(contact_id);
CREATE INDEX IF NOT EXISTS idx_projects_status_code ON projects(status_code);
CREATE INDEX IF NOT EXISTS idx_projects_source_type ON projects(source_type);
CREATE INDEX IF NOT EXISTS idx_projects_inquiry_date ON projects(inquiry_date);
CREATE INDEX IF NOT EXISTS idx_projects_expected_delivery_date ON projects(expected_delivery_date);
CREATE INDEX IF NOT EXISTS idx_projects_has_po ON projects(has_po);
CREATE INDEX IF NOT EXISTS idx_projects_has_3d_model ON projects(has_3d_model);
CREATE INDEX IF NOT EXISTS idx_project_files_project_id ON project_files(project_id);
CREATE INDEX IF NOT EXISTS idx_project_files_category_code ON project_files(category_code);
CREATE INDEX IF NOT EXISTS idx_project_files_extension ON project_files(extension);
CREATE INDEX IF NOT EXISTS idx_project_files_content_hash ON project_files(content_hash);
CREATE INDEX IF NOT EXISTS idx_project_files_import_method ON project_files(import_method);
CREATE INDEX IF NOT EXISTS idx_quotes_project_id ON quotes(project_id);
CREATE INDEX IF NOT EXISTS idx_purchase_orders_project_id ON purchase_orders(project_id);
CREATE INDEX IF NOT EXISTS idx_todos_project_id ON todos(project_id);
CREATE INDEX IF NOT EXISTS idx_todos_status ON todos(status);
CREATE INDEX IF NOT EXISTS idx_todos_due_date ON todos(due_date);
CREATE INDEX IF NOT EXISTS idx_project_events_project_id ON project_events(project_id);

INSERT OR IGNORE INTO project_statuses (code, name, sort_order, is_active) VALUES
('inquiry', '询价录入', 10, 1),
('clarification', '需求澄清', 20, 1),
('solution_design', '方案设计', 30, 1),
('cost_review', '内部评估/成本核算', 40, 1),
('internal_quote', '内部工程师报价', 50, 1),
('quoted', '已向客户报价', 60, 1),
('waiting_feedback', '等待客户反馈', 70, 1),
('po_received', '客户已下 PO', 80, 1),
('purchasing', '备料/采购', 90, 1),
('manufacturing', '装配/制作', 100, 1),
('acceptance', '验收/调试', 110, 1),
('shipped', '已发货', 120, 1),
('completed', '项目完成', 130, 1),
('paused', '暂停', 140, 1),
('lost_closed', '丢单/关闭', 150, 1),
('historical_entry', '历史补录', 160, 1);

INSERT OR IGNORE INTO file_categories (code, name, default_folder, sort_order, is_active) VALUES
('inquiry', '询价需求', '01_询价需求', 10, 1),
('solution', '方案资料', '02_方案资料', 20, 1),
('internal_quote', '内部报价', '03_内部报价', 30, 1),
('customer_quote', '客户报价', '04_客户报价', 40, 1),
('po', 'PO 订单', '05_PO订单', 50, 1),
('drawing_model', '图纸模型', '06_图纸模型', 60, 1),
('acceptance_delivery', '验收发货', '07_验收发货', 70, 1),
('communication', '沟通记录', '08_沟通记录', 80, 1),
('other', '其他', '99_其他', 90, 1);

INSERT OR IGNORE INTO todo_types (code, name, sort_order, is_active) VALUES
('quote_deadline', '报价截止', 10, 1),
('customer_followup', '客户跟进', 20, 1),
('internal_review', '内部评估', 30, 1),
('delivery', '交期提醒', 40, 1),
('acceptance', '验收提醒', 50, 1),
('shipment', '发货提醒', 60, 1),
('historical_cleanup', '历史资料补全', 70, 1),
('other', '其他', 80, 1);

