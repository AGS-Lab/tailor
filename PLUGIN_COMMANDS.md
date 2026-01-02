# Plugin Command System

Tailor uses a **command registry pattern** similar to VSCode and Obsidian, where plugins register commands that can be executed by anyone (UI, other plugins, keyboard shortcuts, etc.).

---

## **How It Works**

### **1. Plugin Registers Commands** (during `__init__`)

```python
class Plugin:
    def __init__(self, emitter, brain):
        self.emitter = emitter
        self.brain = brain
        
        # Register commands
        brain.register_command("myPlugin.doSomething", self.do_something, "myPlugin")
        brain.register_command("myPlugin.getData", self.get_data, "myPlugin")
    
    async def do_something(self, **kwargs):
        """Handler for myPlugin.doSomething command"""
        return {"result": "done"}
    
    async def get_data(self, table: str, **kwargs):
        """Handler for myPlugin.getData command"""
        return {"data": [...]}
```

### **2. Anyone Can Execute Commands**

#### **From UI** (via WebSocket)
```javascript
// Using the request() helper from vault.html
await request('execute_command', {
  command: "myPlugin.doSomething",
  args: { foo: "bar" }
});
```

**Raw JSON-RPC Message:**
```json
{
  "jsonrpc": "2.0",
  "method": "execute_command",
  "params": {
    "command": "myPlugin.doSomething",
    "args": { "foo": "bar" }
  },
  "id": 1
}
```

#### **From Other Plugins** (plugin-to-plugin)
```python
class DatabasePlugin:
    async def query(self, table: str):
        # Call another plugin's command
        result = await self.brain.execute_command("cache.get", key=table)
        if not result:
            # Do actual query
            data = await self.fetch_from_db(table)
            # Tell cache plugin to store it
            await self.brain.execute_command("cache.set", key=table, value=data)
        return result
```

#### **From VaultBrain** (system-level)
```python
# In vault_brain.py or other system code
result = await vault_brain.execute_command("logger.log", message="System started")
```

---

## **Command Registry API**

### **`brain.register_command(command_id, handler, plugin_name)`**

Register a command in the global registry.

**Parameters:**
- `command_id` (str): Unique identifier, typically `pluginName.action`
- `handler` (async function): Function to handle the command
- `plugin_name` (str, optional): Name of plugin registering this command

**Example:**
```python
brain.register_command("database.query", self.query_handler, "database_plugin")
```

### **`await brain.execute_command(command_id, **kwargs)`**

Execute a registered command.

**Parameters:**
- `command_id` (str): Command to execute
- `**kwargs`: Arguments passed to the command handler

**Returns:** Whatever the handler returns

**Raises:** `ValueError` if command not found

**Example:**
```python
result = await brain.execute_command("database.query", table="users", limit=10)
```

### **`brain.get_commands()`**

Get all registered commands (for building command palettes, documentation, etc.).

**Returns:** `Dict[str, Dict]` with structure:
```python
{
  "example.customAction": {"plugin": "example_plugin"},
  "example.getStatus": {"plugin": "example_plugin"},
  "database.query": {"plugin": "database_plugin"}
}
```

---

## **Real-World Examples**

### **Example 1: Database Plugin**

```python
class Plugin:
    def __init__(self, emitter, brain):
        self.emitter = emitter
        self.brain = brain
        self.db = SQLiteDatabase()
        
        # Register database commands
        brain.register_command("database.query", self.query, "database")
        brain.register_command("database.insert", self.insert, "database")
        brain.register_command("database.update", self.update, "database")
    
    async def query(self, table: str, where: dict = None, **kwargs):
        """Query database table"""
        results = self.db.select(table, where)
        return {"rows": results, "count": len(results)}
    
    async def insert(self, table: str, data: dict, **kwargs):
        """Insert into database"""
        row_id = self.db.insert(table, data)
        self.emitter.notify(f"Inserted row {row_id}", severity="success")
        return {"id": row_id}
```

**Usage from other plugin:**
```python
# In analytics plugin
users = await self.brain.execute_command("database.query", table="users", where={"active": True})
print(f"Found {users['count']} active users")
```

---

### **Example 2: Cache Plugin**

```python
class Plugin:
    def __init__(self, emitter, brain):
        self.emitter = emitter
        self.brain = brain
        self.cache = {}
        
        brain.register_command("cache.get", self.get, "cache")
        brain.register_command("cache.set", self.set, "cache")
        brain.register_command("cache.clear", self.clear, "cache")
    
    async def get(self, key: str, **kwargs):
        """Get from cache"""
        return self.cache.get(key)
    
    async def set(self, key: str, value, ttl: int = 3600, **kwargs):
        """Set cache value"""
        self.cache[key] = value
        return {"cached": True}
    
    async def clear(self, pattern: str = None, **kwargs):
        """Clear cache"""
        if pattern:
            # Clear matching keys
            keys_to_delete = [k for k in self.cache if pattern in k]
            for k in keys_to_delete:
                del self.cache[k]
        else:
            self.cache.clear()
        return {"cleared": True}
```

**Usage:**
```python
# Other plugins use cache automatically
await self.brain.execute_command("cache.set", key="user:123", value=user_data)
cached = await self.brain.execute_command("cache.get", key="user:123")
```

---

### **Example 3: API Plugin Calling Database**

```python
class Plugin:
    """API plugin that uses database plugin"""
    
    def __init__(self, emitter, brain):
        self.emitter = emitter
        self.brain = brain
        
        brain.register_command("api.getUsers", self.get_users, "api")
        brain.register_command("api.createUser", self.create_user, "api")
    
    async def get_users(self, active_only: bool = False, **kwargs):
        """Get users via database command"""
        where = {"active": True} if active_only else None
        
        # Call database plugin's command
        result = await self.brain.execute_command(
            "database.query",
            table="users",
            where=where
        )
        
        return result
    
    async def create_user(self, name: str, email: str, **kwargs):
        """Create user and invalidate cache"""
        # Insert into database
        result = await self.brain.execute_command(
            "database.insert",
            table="users",
            data={"name": name, "email": email, "active": True}
        )
        
        # Clear user cache
        await self.brain.execute_command("cache.clear", pattern="user:")
        
        self.emitter.notify(f"Created user: {name}", severity="success")
        return result
```

---

## **Command Naming Conventions**

Follow these conventions for clarity:

### **Format**: `pluginName.actionName`

- Use camelCase for action names
- Keep plugin names lowercase
- Be descriptive but concise

**Examples:**
```python
✅ "database.query"
✅ "cache.get"
✅ "api.createUser"
✅ "filesystem.readFile"
✅ "llm.generateText"

❌ "db_query"           # Missing plugin namespace
❌ "DatabaseQuery"      # Wrong case
❌ "database.q"         # Too abbreviated
```

---

## **Command Discoverability**

### **Building a Command Palette** (Future UI Feature)

```python
# Get all available commands
commands = brain.get_commands()

# Display in UI
for cmd_id, info in commands.items():
    print(f"{cmd_id} - from plugin: {info['plugin']}")

# Output:
# example.customAction - from plugin: example_plugin
# example.getStatus - from plugin: example_plugin
# database.query - from plugin: database_plugin
# cache.get - from plugin: cache_plugin
```

---

## **Benefits of Command Pattern**

### **✅ Compared to Direct Method Calls:**

1. **Decoupling**: Plugins don't need references to each other
2. **Discoverability**: Can list all available commands
3. **Validation**: Commands can be validated before execution
4. **Logging**: Easy to log all command executions
5. **Testing**: Can mock command registry for testing
6. **Hot Reload**: Commands can be registered/unregistered dynamically
7. **Permission System**: Can add permission checks per command (future)
8. **Rate Limiting**: Can throttle command execution (future)

### **✅ Compared to Event Emitter:**

- **Commands**: Request-response (get a result back)
- **Events**: Fire-and-forget (no return value)

**Use commands when you need a response, events for notifications.**

---

## **Error Handling**

```python
try:
    result = await brain.execute_command("database.query", table="users")
except ValueError as e:
    # Command not found
    print(f"Command not registered: {e}")
except Exception as e:
    # Command handler error
    print(f"Command execution failed: {e}")
```

---

## **Future Enhancements**

### **Command Metadata** (Planned)
```python
brain.register_command(
    "database.query",
    self.query,
    plugin_name="database",
    metadata={
        "description": "Query database table",
        "args": {
            "table": {"type": "string", "required": True},
            "where": {"type": "dict", "required": False}
        },
        "returns": "List of rows",
        "category": "Database"
    }
)
```

### **Keyboard Shortcuts** (Planned)
```python
# In .vault.json
{
  "keybindings": {
    "Ctrl+Shift+D": "database.query"
  }
}
```

### **Permission System** (Planned)
```python
brain.register_command(
    "filesystem.delete",
    self.delete,
    permissions=["file.write"]
)
```

---

## **Comparison with Other Systems**

### **VSCode**
```typescript
// Register
vscode.commands.registerCommand('extension.doSomething', () => {
  // handler
});

// Execute
vscode.commands.executeCommand('extension.doSomething');
```

### **Obsidian**
```typescript
// Register
this.addCommand({
  id: 'my-command',
  name: 'My Command',
  callback: () => {
    // handler
  }
});

// Execute
this.app.commands.executeCommandById('my-command');
```

### **Tailor** (This Implementation)
```python
# Register
brain.register_command("myPlugin.doSomething", self.handler, "myPlugin")

# Execute
await brain.execute_command("myPlugin.doSomething")
```

---

## **Migration from Old Pattern**

### **Old (Direct method calls):**
```python
# Plugin A needs direct reference to Plugin B
class PluginA:
    def __init__(self, emitter, plugin_b):
        self.plugin_b = plugin_b
    
    async def do_work(self):
        data = await self.plugin_b.get_data()
```

### **New (Command registry):**
```python
# Plugin A doesn't need to know about Plugin B
class PluginA:
    def __init__(self, emitter, brain):
        self.brain = brain
    
    async def do_work(self):
        data = await self.brain.execute_command("pluginB.getData")
```

**Benefits**: Plugin A works even if Plugin B isn't loaded, loose coupling, easier testing.
