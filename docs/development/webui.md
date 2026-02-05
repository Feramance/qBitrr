# WebUI Development

Guide for developing qBitrr's React-based web interface.

## Quick Start

```bash
cd webui

# Install dependencies
npm ci

# Start development server
npm run dev

# Visit http://localhost:5173
```

The development server proxies API requests to http://localhost:6969 where qBitrr backend should be running.

## Tech Stack

### Core Technologies

- **React 18** - UI library with hooks
- **TypeScript** - Type-safe JavaScript
- **Vite** - Fast build tool with HMR
- **Mantine v8** - Component library
- **React Router** - Client-side routing
- **Axios** - HTTP client

### State Management

- **React Context API** - Global state
  - `SearchContext` - Search state
  - `ToastContext` - Notifications
  - `WebUIContext` - Settings

### UI Components

- **@mantine/core** - Base components (Button, Card, Table, etc.)
- **@mantine/hooks** - React hooks utilities
- **@mantine/notifications** - Toast notifications
- **@tanstack/react-table** - Advanced data tables
- **react-hook-form** - Form validation

## Project Structure

```
webui/
├── public/                  # Static assets
│   ├── favicon.ico
│   ├── manifest.json
│   └── ...
├── src/
│   ├── api/                # API client
│   │   ├── client.ts       # Axios instance
│   │   └── types.ts        # TypeScript interfaces
│   ├── components/         # Reusable components
│   │   ├── ConfirmDialog.tsx
│   │   ├── LogViewer.tsx
│   │   ├── ProcessCard.tsx
│   │   └── ...
│   ├── context/           # Global state
│   │   ├── SearchContext.tsx
│   │   ├── ToastContext.tsx
│   │   └── WebUIContext.tsx
│   ├── hooks/             # Custom hooks
│   │   ├── useDataSync.ts
│   │   ├── useWebSocket.ts
│   │   └── ...
│   ├── icons/             # SVG icons
│   │   └── ...
│   ├── pages/             # Route pages
│   │   ├── Dashboard.tsx
│   │   ├── Processes.tsx
│   │   ├── Logs.tsx
│   │   ├── Radarr.tsx
│   │   ├── Sonarr.tsx
│   │   ├── Lidarr.tsx
│   │   └── Config.tsx
│   ├── utils/             # Helper functions
│   │   └── ...
│   ├── App.tsx            # Root component
│   ├── main.tsx           # Entry point
│   └── vite-env.d.ts      # Vite types
├── index.html             # HTML template
├── package.json           # Dependencies
├── tsconfig.json          # TypeScript config
├── vite.config.ts         # Vite config
└── eslint.config.js       # ESLint config
```

## Development Workflow

### Running Locally

**Terminal 1: Backend**
```bash
# Start qBitrr
qbitrr
```

**Terminal 2: Frontend**
```bash
cd webui
npm run dev
```

Visit http://localhost:5173 for the dev server with HMR.

### Making Changes

**1. Create component:**

```typescript
// src/components/TorrentCard.tsx
import { Card, Text, Badge, Button } from '@mantine/core'
import { FC } from 'react'
import { Torrent } from '@/api/types'

interface Props {
  torrent: Torrent
  onDelete: (hash: string) => void
}

const TorrentCard: FC<Props> = ({ torrent, onDelete }) => {
  return (
    <Card shadow="sm" padding="lg">
      <Text size="lg" weight={500}>{torrent.name}</Text>
      <Badge color={torrent.state === 'completed' ? 'green' : 'blue'}>
        {torrent.state}
      </Badge>
      <Button
        color="red"
        onClick={() => onDelete(torrent.hash)}
      >
        Delete
      </Button>
    </Card>
  )
}

export default TorrentCard
```

**2. Add type definitions:**

```typescript
// src/api/types.ts
export interface Torrent {
  hash: string
  name: string
  state: 'downloading' | 'completed' | 'failed'
  progress: number
  eta: number
  ratio: number
}
```

**3. Create API client method:**

```typescript
// src/api/client.ts
import axios from 'axios'
import { Torrent } from './types'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
  headers: {
    'Authorization': `Bearer ${localStorage.getItem('apiToken') || ''}`
  }
})

export const getTorrents = async (): Promise<Torrent[]> => {
  const { data } = await api.get<Torrent[]>('/torrents')
  return data
}

export const deleteTorrent = async (hash: string): Promise<void> => {
  await api.delete(`/torrents/${hash}`)
}
```

**4. Use in page:**

```typescript
// src/pages/Torrents.tsx
import { FC, useEffect, useState } from 'react'
import { Container, Title } from '@mantine/core'
import { getTorrents, deleteTorrent } from '@/api/client'
import { Torrent } from '@/api/types'
import TorrentCard from '@/components/TorrentCard'

const TorrentsPage: FC = () => {
  const [torrents, setTorrents] = useState<Torrent[]>([])

  useEffect(() => {
    const fetchTorrents = async () => {
      const data = await getTorrents()
      setTorrents(data)
    }
    fetchTorrents()
  }, [])

  const handleDelete = async (hash: string) => {
    await deleteTorrent(hash)
    setTorrents(prev => prev.filter(t => t.hash !== hash))
  }

  return (
    <Container>
      <Title>Torrents</Title>
      {torrents.map(torrent => (
        <TorrentCard
          key={torrent.hash}
          torrent={torrent}
          onDelete={handleDelete}
        />
      ))}
    </Container>
  )
}

export default TorrentsPage
```

## Code Style

See [Code Style Guide](code-style.md#typescriptreact-code-style) for full guidelines.

**Key Points:**

- Functional components only
- Explicit return types
- 2-space indentation
- camelCase for variables/functions
- PascalCase for components/interfaces

**Lint and format:**

```bash
# Lint
npm run lint

# Format (via ESLint --fix)
npm run lint -- --fix
```

## State Management

### Context API

**Create context:**

```typescript
// src/context/TorrentContext.tsx
import { createContext, FC, PropsWithChildren, useState } from 'react'
import { Torrent } from '@/api/types'

interface TorrentContextType {
  torrents: Torrent[]
  addTorrent: (torrent: Torrent) => void
  removeTorrent: (hash: string) => void
}

export const TorrentContext = createContext<TorrentContextType | null>(null)

export const TorrentProvider: FC<PropsWithChildren> = ({ children }) => {
  const [torrents, setTorrents] = useState<Torrent[]>([])

  const addTorrent = (torrent: Torrent) => {
    setTorrents(prev => [...prev, torrent])
  }

  const removeTorrent = (hash: string) => {
    setTorrents(prev => prev.filter(t => t.hash !== hash))
  }

  return (
    <TorrentContext.Provider value={{ torrents, addTorrent, removeTorrent }}>
      {children}
    </TorrentContext.Provider>
  )
}
```

**Use context:**

```typescript
import { useContext } from 'react'
import { TorrentContext } from '@/context/TorrentContext'

const MyComponent = () => {
  const context = useContext(TorrentContext)
  if (!context) throw new Error('Must be used within TorrentProvider')

  const { torrents, addTorrent } = context
  // ...
}
```

## Custom Hooks

**Example: Auto-refresh data**

```typescript
// src/hooks/useDataSync.ts
import { useEffect, useState } from 'react'

export function useDataSync<T>(
  fetcher: () => Promise<T>,
  interval: number = 5000
): [T | null, boolean, Error | null] {
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<Error | null>(null)

  useEffect(() => {
    const fetchData = async () => {
      try {
        const result = await fetcher()
        setData(result)
        setError(null)
      } catch (err) {
        setError(err as Error)
      } finally {
        setLoading(false)
      }
    }

    fetchData() // Initial fetch
    const timer = setInterval(fetchData, interval)

    return () => clearInterval(timer)
  }, [fetcher, interval])

  return [data, loading, error]
}
```

**Usage:**

```typescript
const [torrents, loading, error] = useDataSync(getTorrents, 5000)
```

## Mantine Components

### Common Components

```typescript
import {
  Button, Card, Text, Title,
  Container, Grid, Stack,
  Table, Badge, ActionIcon,
  Modal, TextInput, Select
} from '@mantine/core'

// Button
<Button onClick={handleClick} color="blue">Click Me</Button>

// Card
<Card shadow="sm" padding="lg">
  <Text>Card content</Text>
</Card>

// Table
<Table>
  <thead>
    <tr><th>Name</th><th>Status</th></tr>
  </thead>
  <tbody>
    {data.map(row => (
      <tr key={row.id}>
        <td>{row.name}</td>
        <td><Badge>{row.status}</Badge></td>
      </tr>
    ))}
  </tbody>
</Table>
```

### Notifications

```typescript
import { notifications } from '@mantine/notifications'

// Success notification
notifications.show({
  title: 'Success',
  message: 'Torrent deleted successfully',
  color: 'green'
})

// Error notification
notifications.show({
  title: 'Error',
  message: 'Failed to delete torrent',
  color: 'red'
})
```

### Forms

```typescript
import { useForm } from 'react-hook-form'
import { TextInput, Button } from '@mantine/core'

interface FormData {
  name: string
  category: string
}

const MyForm = () => {
  const { register, handleSubmit, formState: { errors } } = useForm<FormData>()

  const onSubmit = (data: FormData) => {
    console.log(data)
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)}>
      <TextInput
        label="Name"
        {...register('name', { required: 'Name is required' })}
        error={errors.name?.message}
      />
      <Button type="submit">Submit</Button>
    </form>
  )
}
```

## Building for Production

```bash
# Build WebUI
cd webui
npm run build

# Output: webui/dist/
```

**Build includes:**

- Minified JavaScript bundles
- Optimized CSS
- Compressed assets
- Source maps (for debugging)

**Integration with Python package:**

The `setup.py` copies `webui/dist/` to `qBitrr/static/` during package build.

## Testing

**Currently:** Manual testing via browser

**Planned:** Automated testing with:
- **Vitest** - Unit tests
- **Testing Library** - Component tests
- **Playwright** - E2E tests

## Debugging

### Browser DevTools

1. Open Chrome/Firefox DevTools (F12)
2. Check Console for errors
3. Use React DevTools extension
4. Network tab for API calls

### Vite Debug Mode

```bash
# Verbose logging
npm run dev -- --debug
```

### API Request Debugging

Add interceptor to see all requests:

```typescript
// src/api/client.ts
api.interceptors.request.use(request => {
  console.log('Request:', request)
  return request
})

api.interceptors.response.use(response => {
  console.log('Response:', response)
  return response
})
```

## Environment Variables

**Development:**

```env
# webui/.env.development
VITE_API_BASE_URL=http://localhost:6969/api
```

**Production:**

```env
# webui/.env.production
VITE_API_BASE_URL=/api
```

**Usage:**

```typescript
const apiUrl = import.meta.env.VITE_API_BASE_URL
```

## Related Documentation

- [Code Style](code-style.md) - TypeScript/React style guide
- [Development Guide](index.md) - Main development documentation
- [WebUI Features](../webui/index.md) - User-facing WebUI documentation
