# Feed Formulation Admin Dashboard - UI Design Document

## Overview

A modern, multilingual admin dashboard built with Next.js and shadcn UI for managing feed data and API access across multiple countries and organizations.

## Key Features

### 1. Multi-Country Feed Management
- **Country-specific admins**: Each country can have multiple admins
- **Feed CRUD operations**: Create, read, update, delete feeds
- **Bulk operations**: Import/export feeds via Excel
- **Advanced filtering**: By country, type, category, nutritional values
- **Feed validation**: Ensure data quality and completeness

### 2. API Management for Organizations
- **Organization management**: Create and manage organizations
- **API key generation**: Generate secure API keys for organizations
- **Usage tracking**: Monitor API usage per organization
- **Rate limiting**: Set and manage rate limits per organization
- **MCP server integration**: Manage MCP server connections

### 3. User Experience
- **Dark/Light mode**: Seamless theme switching
- **Multilingual**: Support for multiple languages
- **Responsive design**: Works on all devices
- **Accessibility**: WCAG compliant
- **Documentation**: In-app help and guides

## UI Components Structure

### Layout Components
- **Sidebar Navigation**: Collapsible sidebar with navigation
- **Header**: User menu, theme toggle, language selector
- **Breadcrumbs**: Navigation breadcrumbs
- **Footer**: Links and information

### Feed Management Components
- **Feed Table**: Sortable, filterable data table
- **Feed Form**: Create/edit feed with validation
- **Feed Import**: Excel upload and mapping
- **Feed Filters**: Advanced filtering panel
- **Feed Details**: View feed nutritional information

### API Management Components
- **Organization List**: Table of organizations
- **API Key Generator**: Generate new API keys
- **API Key Table**: List and manage API keys
- **Usage Charts**: Visualize API usage
- **Rate Limit Settings**: Configure rate limits

### Shared Components
- **Data Table**: Reusable table component
- **Form Components**: Input, select, textarea with validation
- **Dialogs**: Modal dialogs for confirmations
- **Toast Notifications**: Success/error messages
- **Loading States**: Skeleton loaders and spinners

## Page Structure

### Dashboard (`/`)
- Overview statistics
- Recent activity
- Quick actions
- Charts and graphs

### Feeds (`/feeds`)
- Feed list table
- Filters sidebar
- Add/Edit feed dialog
- Bulk import dialog
- Feed details view

### Countries (`/countries`)
- Country list
- Country admin management
- Feed counts per country
- Country activation toggle

### Organizations (`/organizations`)
- Organization list
- Create organization form
- Organization settings
- Admin management

### API Keys (`/api-keys`)
- API key list by organization
- Generate API key dialog
- Usage statistics
- Revoke/regenerate actions

### Settings (`/settings`)
- User profile
- Preferences
- Language selection
- Theme selection

## Design Principles

1. **Clean & Minimal**: Focus on content, reduce clutter
2. **Consistent**: Use design system consistently
3. **Accessible**: WCAG 2.1 AA compliance
4. **Fast**: Optimize for performance
5. **Documented**: Clear labels and help text

## Color Scheme

### Light Mode
- Background: `#ffffff`
- Surface: `#f9fafb`
- Text: `#111827`
- Primary: `#2563eb`
- Success: `#10b981`
- Warning: `#f59e0b`
- Error: `#ef4444`

### Dark Mode
- Background: `#0f172a`
- Surface: `#1e293b`
- Text: `#f1f5f9`
- Primary: `#3b82f6`
- Success: `#22c55e`
- Warning: `#fbbf24`
- Error: `#f87171`

## Typography

- **Font Family**: Inter (system font fallback)
- **Headings**: Bold, larger sizes
- **Body**: Regular, readable sizes
- **Code**: Monospace font

## Spacing

- **Base unit**: 4px
- **Consistent spacing**: Use Tailwind spacing scale
- **Component padding**: 16px-24px
- **Section spacing**: 32px-48px

## Responsive Breakpoints

- **Mobile**: < 640px
- **Tablet**: 640px - 1024px
- **Desktop**: > 1024px

## Accessibility

- **Keyboard navigation**: Full keyboard support
- **Screen readers**: ARIA labels and roles
- **Focus indicators**: Visible focus states
- **Color contrast**: WCAG AA compliant
- **Alt text**: Images have descriptive alt text

## Performance

- **Code splitting**: Route-based splitting
- **Image optimization**: Next.js Image component
- **Lazy loading**: Load components on demand
- **Caching**: API response caching
- **Bundle size**: Keep bundle size minimal

