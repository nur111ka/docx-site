import sqlite3
import hashlib
import os
import json
from datetime import datetime
from config import Config

def get_db():
    """Создать подключение к БД."""
    conn = sqlite3.connect(Config.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Инициализировать базу данных."""
    conn = get_db()
    c = conn.cursor()
    
    # Таблица шаблонов
    c.execute('''
        CREATE TABLE IF NOT EXISTS templates (
            name TEXT PRIMARY KEY,
            display_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Таблица полей шаблонов
    c.execute('''
        CREATE TABLE IF NOT EXISTS template_fields (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            template_name TEXT NOT NULL,
            field_name TEXT NOT NULL,
            field_label TEXT NOT NULL,
            field_type TEXT DEFAULT 'text',
            field_order INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(template_name, field_name),
            FOREIGN KEY (template_name) REFERENCES templates(name) ON DELETE CASCADE
        )
    ''')
    
    # Таблица JSON замен
    c.execute('''
        CREATE TABLE IF NOT EXISTS template_replacements (
            template_name TEXT PRIMARY KEY,
            replacements_json TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (template_name) REFERENCES templates(name) ON DELETE CASCADE
        )
    ''')
    
    # Таблица API ключей
    c.execute('''
        CREATE TABLE IF NOT EXISTS api_keys (
            api_key TEXT PRIMARY KEY,
            template_name TEXT NOT NULL,
            limit_count INTEGER DEFAULT 10,
            used_count INTEGER DEFAULT 0,
            status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (template_name) REFERENCES templates(name) ON DELETE CASCADE
        )
    ''')
    
    # Таблица логов использования (ДОБАВИТЬ!)
    c.execute('''
        CREATE TABLE IF NOT EXISTS usage_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            api_key TEXT,
            client_ip TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT,
            details TEXT
        )
    ''')
    
    conn.commit()
    conn.close()
    print("✅ База данных инициализирована")

# ===== ФУНКЦИИ ДЛЯ ШАБЛОНОВ =====

def create_template(template_name, display_name):
    """Создать новый шаблон."""
    conn = get_db()
    c = conn.cursor()
    try:
        c.execute('INSERT OR IGNORE INTO templates (name, display_name) VALUES (?, ?)',
                  (template_name, display_name))
        conn.commit()
        return True
    except:
        return False
    finally:
        conn.close()

def delete_template(template_name):
    """Удалить шаблон и все его поля."""
    conn = get_db()
    c = conn.cursor()
    c.execute('DELETE FROM templates WHERE name = ?', (template_name,))
    conn.commit()
    conn.close()

def get_all_templates():
    """Получить все шаблоны."""
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT name, display_name FROM templates ORDER BY created_at')
    templates = c.fetchall()
    conn.close()
    return templates

def get_template_fields(template_name):
    """Получить поля для конкретного шаблона."""
    conn = get_db()
    c = conn.cursor()
    c.execute('''
        SELECT field_name, field_label, field_type, field_order 
        FROM template_fields 
        WHERE template_name = ? 
        ORDER BY field_order
    ''', (template_name,))
    fields = c.fetchall()
    conn.close()
    return fields

def add_field_to_template(template_name, field_name, field_label, field_type='text'):
    """Добавить поле к шаблону."""
    conn = get_db()
    c = conn.cursor()
    try:
        # Получаем максимальный порядок
        c.execute('SELECT MAX(field_order) as max_order FROM template_fields WHERE template_name = ?',
                  (template_name,))
        result = c.fetchone()
        max_order = result['max_order'] if result and result['max_order'] is not None else 0
        
        c.execute('''
            INSERT INTO template_fields (template_name, field_name, field_label, field_type, field_order)
            VALUES (?, ?, ?, ?, ?)
        ''', (template_name, field_name, field_label, field_type, max_order + 1))
        
        conn.commit()
        return True
    except Exception as e:
        print(f"Ошибка добавления поля: {e}")
        return False
    finally:
        conn.close()

def delete_field_from_template(template_name, field_name):
    """Удалить поле из шаблона."""
    conn = get_db()
    c = conn.cursor()
    c.execute('DELETE FROM template_fields WHERE template_name = ? AND field_name = ?',
              (template_name, field_name))
    conn.commit()
    conn.close()

def update_field_in_template(template_name, field_name, field_label, field_type):
    """Обновить поле в шаблоне."""
    conn = get_db()
    c = conn.cursor()
    c.execute('''
        UPDATE template_fields 
        SET field_label = ?, field_type = ?
        WHERE template_name = ? AND field_name = ?
    ''', (field_label, field_type, template_name, field_name))
    conn.commit()
    conn.close()

def save_template_replacements(template_name, replacements_json):
    """Сохранить JSON замен для шаблона."""
    conn = get_db()
    c = conn.cursor()
    
    # Проверяем существование
    c.execute('SELECT 1 FROM template_replacements WHERE template_name = ?', (template_name,))
    exists = c.fetchone()
    
    if exists:
        c.execute('''
            UPDATE template_replacements 
            SET replacements_json = ?, updated_at = CURRENT_TIMESTAMP
            WHERE template_name = ?
        ''', (replacements_json, template_name))
    else:
        c.execute('''
            INSERT INTO template_replacements (template_name, replacements_json)
            VALUES (?, ?)
        ''', (template_name, replacements_json))
    
    conn.commit()
    conn.close()

def get_template_replacements(template_name):
    """Получить JSON замен для шаблона."""
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT replacements_json FROM template_replacements WHERE template_name = ?', 
              (template_name,))
    result = c.fetchone()
    conn.close()
    return result['replacements_json'] if result else '{}'

# ===== ФУНКЦИИ ДЛЯ API КЛЮЧЕЙ =====

def generate_key(template_name, limit_count=10):
    """Сгенерировать ключ для конкретного шаблона."""
    raw_key = f"{template_name}_{datetime.now().timestamp()}_{os.urandom(16).hex()}"
    api_key = hashlib.sha256(raw_key.encode()).hexdigest()[:32]
    
    conn = get_db()
    c = conn.cursor()
    c.execute('''
        INSERT INTO api_keys (api_key, template_name, limit_count)
        VALUES (?, ?, ?)
    ''', (api_key, template_name, limit_count))
    
    conn.commit()
    conn.close()
    return api_key

def check_key(api_key):
    """Проверить API ключ и вернуть имя шаблона."""
    conn = get_db()
    c = conn.cursor()
    c.execute('''
        SELECT template_name, limit_count, used_count, status 
        FROM api_keys 
        WHERE api_key = ? AND status = 'active'
    ''', (api_key,))
    
    row = c.fetchone()
    conn.close()
    
    if not row:
        return False, "❌ Неверный или неактивный ключ"
    
    template_name, limit_count, used_count, status = row
    
    if used_count >= limit_count:
        return False, f"❌ Лимит использований исчерпан ({used_count}/{limit_count})"
    
    return True, template_name

def get_key_info(api_key):
    """Получить информацию о ключе."""
    conn = get_db()
    c = conn.cursor()
    c.execute('''
        SELECT limit_count, used_count, template_name, status 
        FROM api_keys 
        WHERE api_key = ?
    ''', (api_key,))
    
    row = c.fetchone()
    conn.close()
    return row if row else None

def increment_usage(api_key, client_ip, status, details=""):
    """Увеличить счётчик использования ключа и записать лог."""
    conn = get_db()
    c = conn.cursor()
    
    try:
        # Увеличиваем счётчик использования
        c.execute('''
            UPDATE api_keys 
            SET used_count = used_count + 1 
            WHERE api_key = ?
        ''', (api_key,))
        
        # Логируем использование
        c.execute('''
            INSERT INTO usage_logs (api_key, client_ip, status, details)
            VALUES (?, ?, ?, ?)
        ''', (api_key, client_ip, status, details))
        
        conn.commit()
        return True
    except Exception as e:
        print(f"Ошибка increment_usage: {e}")
        return False
    finally:
        conn.close()

def get_all_keys():
    """Получить все ключи."""
    conn = get_db()
    c = conn.cursor()
    c.execute('''
        SELECT api_key, template_name, limit_count, used_count, created_at, status
        FROM api_keys 
        ORDER BY created_at DESC
    ''')
    keys = c.fetchall()
    conn.close()
    return keys

def deactivate_key(api_key):
    """Деактивировать ключ."""
    conn = get_db()
    c = conn.cursor()
    c.execute('UPDATE api_keys SET status = "inactive" WHERE api_key = ?', (api_key,))
    conn.commit()
    conn.close()

def get_usage_stats():
    """Получить статистику использования."""
    conn = get_db()
    c = conn.cursor()
    
    c.execute('SELECT COUNT(*) as total_requests FROM usage_logs')
    total = c.fetchone()['total_requests']
    
    c.execute('SELECT COUNT(*) as active_keys FROM api_keys WHERE status = "active"')
    active = c.fetchone()['active_keys']
    
    conn.close()
    return {'total_requests': total or 0, 'active_keys': active or 0}

def check_rate_limit(api_key, client_ip, limit_requests, limit_period):
    """Проверить rate limit."""
    conn = get_db()
    c = conn.cursor()
    
    c.execute('''
        SELECT COUNT(*) as count 
        FROM usage_logs 
        WHERE api_key = ? AND client_ip = ? 
        AND timestamp > datetime('now', ? || ' seconds')
    ''', (api_key, client_ip, f"-{limit_period}"))
    
    result = c.fetchone()
    conn.close()
    
    if result and result['count'] >= limit_requests:
        return False, f"❌ Слишком много запросов. Подождите {limit_period} секунд."
    
    return True, "✅ Лимит не превышен"