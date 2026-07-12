# Security Rules & Coding Standards

## Rule 1: No Hardcoded Secrets
All secrets — API keys, passwords, tokens, connection strings, and cryptographic keys — must never appear in source code. Use environment variables or a secrets manager instead.

**Bad:**
```python
API_KEY = "sk-1234567890abcdef"
```
```javascript
const dbPassword = "password123";
```

**Good:**
```python
import os
API_KEY = os.environ.get("API_KEY")
```
```javascript
const dbPassword = process.env.DB_PASSWORD;
```

## Rule 2: SQL Injection Prevention
Use parameterized queries or an ORM. Never concatenate user input directly into SQL strings.

**Bad:**
```python
query = f"SELECT * FROM users WHERE id = {user_input}"
cursor.execute(query)
```

**Good:**
```python
query = "SELECT * FROM users WHERE id = ?"
cursor.execute(query, (user_input,))
```

## Rule 3: Validate All User Input
All data received from users, API requests, or external sources must be validated for type, length, format, and range before use. Never trust raw input.

**Bad:**
```javascript
function processUser(data) {
    db.save(data.email);  // No validation
}
```

**Good:**
```javascript
function processUser(data) {
    if (!data.email || !data.email.includes('@')) {
        throw new Error('Invalid email');
    }
    db.save(data.email);
}
```

## Rule 4: No Sensitive Data in Logs
Never log passwords, tokens, credit card numbers, personal data, or any information that could help an attacker. Use structured logging with redaction.

**Bad:**
```python
logging.info(f"User login: {username}, password: {password}")
```

**Good:**
```python
logging.info(f"User login attempt: {username}")
```

## Rule 5: Use Environment Variables for Configuration
All configuration values that differ between environments (development, staging, production) must be loaded from environment variables, not hardcoded.

**Bad:**
```javascript
const apiUrl = "https://prod-api.company.com";
const debug = false;
```

**Good:**
```javascript
const apiUrl = process.env.API_URL;
const debug = process.env.NODE_ENV !== "production";
```

## Rule 6: Python — Use `os.environ.get()` for Secrets
In Python applications, always use `os.environ.get()` or `os.getenv()` to read secrets. Never hardcode them in source files, configuration files, or version control.

**Bad:**
```python
DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
```

**Good:**
```python
import os
DATABASE_URL = os.environ.get("DATABASE_URL")
```

## Rule 7: JavaScript — Never Commit `.env` Files
Environment files (.env, .env.local, .env.production) must be added to .gitignore. Only commit .env.example as a template. Never commit actual secrets.

**Bad:**
```
# .gitignore
node_modules/
```

**Good:**
```
# .gitignore
node_modules/
.env
.env.local
.env.production
```

## Rule 8: TypeScript — Use Strict Type Checking for User Input
When processing user input in TypeScript, define proper interfaces and validate types at runtime. Never use `any` for user-provided data.

**Bad:**
```typescript
function handleRequest(data: any) {
    return db.query(data.query);
}
```

**Good:**
```typescript
interface RequestData {
    userId: string;
    action: 'read' | 'write';
}

function handleRequest(data: unknown) {
    const validated = validateRequest(data);
    return db.query(validated.userId);
}