---
name: release-plugin
description: Build, test, and maintain container-based integration plugins for Digital.ai Release using the Python SDK. Covers project setup, type definitions, task implementation, unit testing, server connections, build/deploy workflow, and production Kubernetes configuration.
license: MIT
compatibility: opencode
metadata:
  audience: developers
  workflow: digital-ai-release
---

## What I do

Guide developers through building container-based integration plugins for Digital.ai Release using the Python Integration SDK. This includes:

- Setting up and configuring a plugin project from the template
- Defining task types and server connections in `type-definitions.yaml`
- Implementing task logic in Python using the `digitalai-release-sdk`
- Writing and running unit tests
- Building, packaging, and installing plugins into a Release server
- Integrating with third-party services and APIs
- Troubleshooting common development issues

## When to use me

Use this skill when:

- Creating a new Digital.ai Release integration plugin
- Adding new tasks, server connections, or scripts to an existing plugin
- Modifying `type-definitions.yaml` to define or change types
- Writing or updating Python task implementations
- Debugging plugin build, install, or runtime issues
- Setting up the development environment (Docker Compose, container registry)
- Preparing a plugin for production deployment on Kubernetes

---

## Architecture overview

A container-based Release integration plugin has two deliverables:

1. **Plugin ZIP** -- Contains metadata (`type-definitions.yaml`, `plugin-version.properties`, icons) that is uploaded to the Release server. This tells Release what tasks, server types, and scripts exist.
2. **Docker image** -- Contains the Python source code and dependencies. This image is pushed to a container registry and pulled by the Release Remote Runner when a task executes.

At runtime, the Release Remote Runner launches a container from the Docker image, and the SDK wrapper (`digitalai.release.integration.wrapper`) discovers the Python class matching the task type and calls its `execute()` method.

---

## Project structure

```
<project-root>/
  project.properties          # Plugin name, version, registry URL and org
  requirements.txt            # Python dependencies (must include digitalai-release-sdk)
  Dockerfile                  # Container image definition
  build.sh / build.bat        # Build scripts (zip, image, upload)
  xlw / xlw.bat               # XL CLI wrapper for plugin upload
  .xebialabs/
    config.yaml               # Release server connection for upload
    wrapper.conf              # XL CLI version
  resources/
    type-definitions.yaml     # Type/task/server definitions (YAML format)
    plugin-version.properties # Templated version manifest
    *.png                     # Task icons
  src/
    *.py                      # Python task implementations (one class per file)
  tests/
    test_*.py                 # Unit tests (unittest)
  dev-environment/
    docker-compose.yaml       # Local dev: Release server, runner, registry
    .env                      # Environment variables
```

---

## Naming conventions

### Project naming

Follow the pattern: `[publisher]-release-[target]-integration`

- `publisher` = company or developer name
- `target` = the system being integrated with

Examples: `acme-release-aws-integration`, `hes-release-workshop-integration`

### Type naming

Types in `type-definitions.yaml` use a namespace prefix: `<namespace>.<TypeName>`

- The namespace groups all types in a plugin (e.g. `aws`, `jira`, `containerExamples`)
- Type names use PascalCase
- The Python class name must match the type name (without namespace)

Example: type `aws.CreateBucket` maps to Python class `CreateBucket`.

---

## Key file: `project.properties`

Central configuration read by `build.sh`:

```properties
PLUGIN=publisher-release-target-integration
VERSION=0.0.1
REGISTRY_URL=container-registry:5050
REGISTRY_ORG=digitalai
```

Update `PLUGIN` to match your project name. Bump `VERSION` for each release. The `REGISTRY_URL` and `REGISTRY_ORG` compose the Docker image path: `REGISTRY_URL/REGISTRY_ORG/PLUGIN:VERSION`.

---

## Key file: `type-definitions.yaml`

This YAML file defines all types recognized by Digital.ai Release. It uses placeholder tokens (`@project.name@`, `@project.version@`, `@registry.url@`, `@registry.org@`) that are substituted at build time.

### Base task type (virtual)

Every plugin should define a virtual base task that sets the container image, icon, and color for all tasks:

```yaml
types:
  myNamespace.BaseTask:
    extends: xlrelease.ContainerTask
    virtual: true
    hidden-properties:
      image:
        default: "@registry.url@/@registry.org@/@project.name@:@project.version@"
        transient: true
      iconLocation: my-icon.png
      taskColor: "#667385"
```

### Simple task type

```yaml
  myNamespace.Hello:
    extends: myNamespace.BaseTask
    description: "Simple greeter task"
    input-properties:
      yourName:
        description: The name to greet
        kind: string
        default: World
    output-properties:
      greeting:
        kind: string
```

### Server connection type

For integrating with external services, define a server type extending `configuration.BasicAuthHttpConnection`:

```yaml
  myNamespace.Server:
    extends: configuration.BasicAuthHttpConnection
    properties:
      url:
        default: https://api.example.com
        description: Server URL
        required: true
    hidden-properties:
      testConnectionScript: myNamespace.TestConnection
```

### Task that uses a server connection

Reference the server type using `kind: ci` with `referenced-type`:

```yaml
  myNamespace.QueryTask:
    extends: myNamespace.BaseTask
    description: "Query the external server"
    input-properties:
      server:
        kind: ci
        referenced-type: myNamespace.Server
      itemId:
        kind: string
    output-properties:
      result:
        kind: string
```

### Base script type (for test connections, lookups)

```yaml
  myNamespace.BaseScript:
    extends: xlrelease.RemoteScriptExecution
    virtual: true
    hidden-properties:
      image:
        default: "@registry.url@/@registry.org@/@project.name@:@project.version@"
        transient: true
    output-properties:
      commandResponse:
        kind: map_string_string
```

### Test connection script

```yaml
  myNamespace.TestConnection:
    extends: myNamespace.BaseScript
    input-properties:
      server:
        kind: ci
        referenced-type: myNamespace.Server
```

### Lookup script (for dropdown inputs)

```yaml
  myNamespace.NameLookup:
    extends: myNamespace.BaseScript
    input-properties:
      _ci:
        kind: ci
        referenced-type: myNamespace.BaseTask
        required: true
      _attributes:
        kind: map_string_string
        required: true
      _parameters:
        kind: ci
        referenced-type: udm.Parameters
        required: true
```

### Task with lookup-enabled input

```yaml
  myNamespace.TaskWithLookup:
    extends: myNamespace.BaseTask
    description: "Task with dropdown lookup"
    input-properties:
      selectedValue:
        description: Choose a value
        kind: string
        input-hint:
          method-ref: valueLookup
    methods:
      valueLookup:
        delegate: remoteScriptLookup
        script: myNamespace.NameLookup
    output-properties:
      result:
        kind: string
```

### Property kinds reference

| Kind | Description |
|------|-------------|
| `string` | Text value |
| `integer` | Integer number |
| `boolean` | True/false |
| `ci` | Reference to a configuration item (server, etc.) |
| `map_string_string` | Map of string key-value pairs |
| `list_of_string` | List of strings |
| `date` | Date value |

---

## Python task implementation

### Pattern

Every task class:

1. Extends `BaseTask` from `digitalai.release.integration`
2. Implements `execute(self) -> None`
3. Reads inputs from `self.input_properties` (a dict keyed by property names from `type-definitions.yaml`)
4. Sets outputs via `self.set_output_property(name, value)`
5. Adds UI comments via `self.add_comment(text)`
6. Gets the Release API client via `self.get_release_api_client()` (when needed)

### Simple task example

```python
from digitalai.release.integration import BaseTask

class Hello(BaseTask):
    """Creates a greeting based on a name"""

    def execute(self) -> None:
        name = self.input_properties['yourName']
        if not name:
            raise ValueError("The 'yourName' field cannot be empty")

        greeting = f"Hello {name}"
        self.add_comment(greeting)
        self.set_output_property('greeting', greeting)
```

### Server connection task example

```python
import requests
from digitalai.release.integration import BaseTask

class ServerQuery(BaseTask):
    """Fetches data from a remote server"""

    def execute(self) -> None:
        server = self.input_properties['server']
        if server is None:
            raise ValueError("Server field cannot be empty")

        server_url = server['url'].strip("/")
        auth = (server['username'], server['password'])
        item_id = self.input_properties['itemId']
        request_url = f"{server_url}/items/{item_id}"

        self.add_comment(f"Sending request to {request_url}")
        response = requests.get(request_url, auth=auth)
        response.raise_for_status()

        result = response.json()['name']
        self.set_output_property('result', result)
```

### Release API task example

```python
from digitalai.release.integration import BaseTask

class SetSystemMessage(BaseTask):
    """Sets the system message using the Release API client"""

    def execute(self) -> None:
        message = self.input_properties['message']
        if not message:
            raise ValueError("The 'Message' field cannot be empty")

        release_api_client = self.get_release_api_client()
        system_message = {
            "type": "xlrelease.SystemMessageSettings",
            "id": "Configuration/settings/SystemMessageSettings",
            "message": message,
            "enabled": "True",
            "automated": "False"
        }
        release_api_client.put("/api/v1/config/system-message", json=system_message)
        self.add_comment(f'System message updated to "{message}"')
```

### Test connection script example

```python
import requests
from digitalai.release.integration import BaseTask

class TestConnection(BaseTask):
    """Tests connectivity to the remote server"""

    def execute(self) -> None:
        try:
            server = self.input_properties['server']
            server_url = server['url'].strip("/")
            auth = (server['username'], server['password'])

            response = requests.get(server_url, auth=auth)
            response.raise_for_status()
            result = {"success": True, "output": "Connection success"}
        except Exception as e:
            result = {"success": False, "output": str(e)}
        finally:
            self.set_output_property("commandResponse", result)
```

### Lookup script example

```python
from digitalai.release.integration import BaseTask

class NameLookup(BaseTask):
    """Returns a list of label/value pairs for UI dropdowns"""

    def execute(self) -> None:
        result = [
            {'label': 'Option A', 'value': 'option_a'},
            {'label': 'Option B', 'value': 'option_b'},
        ]
        self.set_output_property("commandResponse", result)
```

### Important rules

- The Python class name MUST match the type name (without namespace prefix) in `type-definitions.yaml`
- Files go in the `src/` directory
- One class per file is recommended
- The SDK discovers classes automatically by matching type names to class names
- Use `raise ValueError(...)` or `raise Exception(...)` to signal task failure
- The `requests` library is included via the SDK; add other libraries to `requirements.txt`

---

## Unit testing

Tests use Python's built-in `unittest` framework. Place test files in `tests/`.

### Test pattern

```python
import unittest
from src.my_task import MyTask

class TestMyTask(unittest.TestCase):

    def test_basic(self):
        # Given
        task = MyTask()
        task.input_properties = {
            'task_id': 'task_1',
            'inputField': 'some_value'
        }

        # When
        task.execute_task()

        # Then
        self.assertEqual(task.get_output_properties()['outputField'], 'expected_value')

if __name__ == '__main__':
    unittest.main()
```

### Test with server connection

```python
import unittest
from src.server_task import ServerTask

class TestServerTask(unittest.TestCase):

    def test_query(self):
        task = ServerTask()
        task.input_properties = {
            'task_id': 'task_1',
            'server': {
                'url': 'https://api.example.com',
                'username': 'user',
                'password': 'pass',
                'authenticationMethod': 'Basic'
            },
            'itemId': '42'
        }
        task.execute_task()
        self.assertIsNotNone(task.get_output_properties()['result'])

if __name__ == '__main__':
    unittest.main()
```

### Running tests

```bash
python -m unittest discover tests
```

Key points:
- Always include `'task_id'` in `input_properties` for tests
- Call `task.execute_task()` (not `task.execute()`) -- this wraps execution with proper error handling
- Access outputs via `task.get_output_properties()`
- For server tasks, provide the full server dict with `url`, `username`, `password`, `authenticationMethod`

---

## Build and deploy workflow

### Build commands

```bash
# Build both zip and Docker image, push image to registry
sh build.sh

# Build only the zip file
sh build.sh --zip

# Build only the Docker image
sh build.sh --image

# Build everything and upload zip to Release server
sh build.sh --upload
```

Windows: use `build.bat` with the same flags.

### What the build does

1. Reads `project.properties`
2. Copies `resources/` to a `tmp/` directory
3. Substitutes placeholders (`@project.name@`, `@project.version@`, `@registry.url@`, `@registry.org@`) in `type-definitions.yaml` and `plugin-version.properties`
4. Zips the processed resources into `build/<PLUGIN>-<VERSION>.zip`
5. Builds Docker image tagged `<REGISTRY_URL>/<REGISTRY_ORG>/<PLUGIN>:<VERSION>`
6. Pushes the Docker image to the container registry
7. (With `--upload`) Installs the zip into Release via `xlw`

### Manual plugin install

```bash
./xlw plugin release install --file build/<PLUGIN>-<VERSION>.zip
```

After install, refresh the Release UI browser -- no server restart needed.

---

## Development environment

The `dev-environment/` directory provides a Docker Compose setup with:

| Service | Port | Purpose |
|---------|------|---------|
| `digitalai-release` | 5516 | Release server (login: admin/admin) |
| `digitalai-release-setup` | -- | Applies initial configuration |
| `digitalai-release-remote-runner` | -- | Executes container tasks in Docker mode |
| `container-registry` | 5050 | Docker registry for plugin images |
| `container-registry-ui` | 8086 | Web UI for the registry |

### Start the development environment

```bash
cd dev-environment
docker compose up -d --build
```

Wait for the Release server log to show: `Digital.ai Release has started.`

Then open http://localhost:5516 (admin/admin).

### Required hosts file entries

Add to `/etc/hosts` (Unix/macOS) or `C:\Windows\System32\drivers\etc\hosts` (Windows):

```
127.0.0.1 digitalai.release.local
127.0.0.1 container-registry
127.0.0.1 host.docker.internal
```

### Reset the environment

```bash
cd dev-environment
docker compose down
docker compose up -d --build
```

---

## Development workflow (step by step)

When creating a new integration plugin from scratch:

1. **Create project** from the template repository on GitHub ("Use this template")
2. **Update `project.properties`** with your plugin name
3. **Set up Python virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate   # or venv\Scripts\activate on Windows
   pip install -r requirements.txt
   ```
4. **Clean up template files** -- remove sample src and test files you don't need
5. **Define types** in `resources/type-definitions.yaml`:
   - Rename the namespace (e.g. `containerExamples` to your own)
   - Define your BaseTask, task types, server types, scripts
6. **Implement Python classes** in `src/` -- one file per task/script
7. **Write unit tests** in `tests/` and run with `python -m unittest discover tests`
8. **Build and install**: `sh build.sh --upload`
9. **Test in Release UI**: create a template, add your task, run it
10. **Iterate**: fix issues, re-build, re-test

### Adding a third-party library

1. Find the package on [pypi.org](https://pypi.org)
2. Add it to `requirements.txt` with a pinned version: `boto3==1.34.127`
3. Run `pip install -r requirements.txt`
4. Import and use in your task code
5. The Dockerfile will install it automatically during image build

---

## Integration with third-party servers

### Checklist for a new integration

- [ ] Create project from template and update project properties
- [ ] Configure IDE and create Python virtual environment
- [ ] Add required libraries to `requirements.txt` and `pip install`
- [ ] Remove unneeded sample files
- [ ] Create skeleton implementation and tests
- [ ] Set up integration test infrastructure (e.g. Localstack for AWS, mock server, etc.)
- [ ] Develop and test iteratively
- [ ] Define types in `type-definitions.yaml`
- [ ] Build, install, and test in Release

### Adding a local test environment

Append services to `dev-environment/docker-compose.yaml` for local testing. Example for Localstack (AWS):

```yaml
  localstack:
    image: localstack/localstack
    ports:
      - "4566:4566"
      - "4510-4559:4510-4559"
    environment:
      - DEBUG=${DEBUG-}
      - DOCKER_HOST=unix:///var/run/docker.sock
    volumes:
      - "${LOCALSTACK_VOLUME_DIR:-./localstack}:/var/lib/localstack"
      - "/var/run/docker.sock:/var/run/docker.sock"
```

When configuring the server endpoint in Release UI for local Docker services, use `http://host.docker.internal:<port>`.

---

## Dockerfile reference

The standard plugin Dockerfile:

```dockerfile
FROM python:alpine3.21

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN mkdir /app && chmod -R 777 /app
WORKDIR /app

COPY . .
RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "-m", "digitalai.release.integration.wrapper"]
```

The entrypoint `digitalai.release.integration.wrapper` is the SDK's task runner. It receives the task type and input properties, discovers the matching Python class, and calls `execute()`.

---

## Troubleshooting

### Release won't start (duplicate type definition)

```
java.lang.IllegalStateException: Trying to register duplicate definition for type (...)
```

**Fix**: Reset the dev environment:
```bash
cd dev-environment && docker compose down && docker compose up -d --build
```

### Release stuck on changelog lock

```
Waiting for changelog lock....
```

**Fix**: Same reset as above.

### Task doesn't show up in the Add task menu

**Fix**: Refresh your browser (hard refresh: Ctrl+Shift+R).

### Task shows up but properties are missing

**Fix**: Refresh your browser.

### Type not found error

```
java.lang.NullPointerException: Could not find a type definition associated with type [...]
```

**Fix**: Ensure the type names in `type-definitions.yaml` are consistent -- especially the `extends` references. Reset dev environment if needed.

### M1/M2 Mac: qemu segfault

**Fix**: Upgrade to macOS Ventura and enable Rosetta in Docker Desktop under "Features in development".

### Docker Compose won't start (port conflicts)

Ensure nothing else is running on ports: 5516 (Release), 5050 (registry), 8086 (registry UI), 4566 (Localstack if used).

### Build fails: image push error

Ensure `container-registry` is in your hosts file and the registry container is running. Check with:
```bash
curl http://container-registry:5050/v2/_catalog
```

### Unit test fails: KeyError on output property

The task's `execute()` method likely raised an error before setting output properties. Check the test output for the underlying exception traceback.

---

## Production deployment with Kubernetes

For production use, container-based plugins run on a Kubernetes cluster via the Release Runner.

### How it works

- The Release Runner lives inside Kubernetes and registers itself with the Release server
- It establishes an outbound connection to the Release server (no inbound access needed to K8s)
- When a task executes, the runner launches a pod with the plugin's container image
- The runner handles communication between the task pod and the Release server

### Prerequisites for Kubernetes setup

- Access to a Kubernetes cluster (Docker Desktop K8s, minikube, or cloud)
- `kubectl` installed and configured
- `helm` installed
- `yq` command-line YAML processor
- A Java JDK (for the `keytool` command used by `xl`)
- `k9s` (optional, for cluster management)

### Key considerations

- The Release server does NOT need to run inside Kubernetes
- The Release Runner connects outbound to the Release server URL
- Plugin container images must be accessible from the Kubernetes cluster
- For local development with K8s, add host entries for `container-registry` and `digitalai.release.local`
