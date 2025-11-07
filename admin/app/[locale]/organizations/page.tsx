'use client';

import { useTranslations } from '@/hooks/use-translations';
import { DashboardLayout } from '@/components/layout/dashboard-layout';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { useQuery } from '@tanstack/react-query';
import { organizationsApi } from '@/lib/api';
import { Link } from '@/lib/navigation';

export default function OrganizationsPage() {
  const t = useTranslations('organizations');
  const tCommon = useTranslations('common');
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false);

  // Fetch organizations
  const { data: organizations = [], refetch } = useQuery({
    queryKey: ['organizations'],
    queryFn: () => organizationsApi.getAll('admin-user-id').then(res => res.data),
  });

  return (
    <DashboardLayout>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">{t('title')}</h1>
            <p className="text-muted-foreground">
              Manage organizations and their API access
            </p>
          </div>
          <Dialog open={isCreateDialogOpen} onOpenChange={setIsCreateDialogOpen}>
            <DialogTrigger asChild>
              <Button>
                <Plus className="mr-2 h-4 w-4" />
                {t('createOrg')}
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>{t('createOrg')}</DialogTitle>
                <DialogDescription>
                  Create a new organization to manage API access
                </DialogDescription>
              </DialogHeader>
              <CreateOrganizationForm
                onSuccess={() => {
                  setIsCreateDialogOpen(false);
                  refetch();
                }}
              />
            </DialogContent>
          </Dialog>
        </div>

        {/* Organizations Grid */}
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {organizations.length === 0 ? (
            <Card className="col-span-full">
              <CardContent className="flex flex-col items-center justify-center py-12">
                <Building2 className="h-12 w-12 text-muted-foreground mb-4" />
                <p className="text-muted-foreground mb-4">No organizations yet</p>
                <Button onClick={() => setIsCreateDialogOpen(true)}>
                  <Plus className="mr-2 h-4 w-4" />
                  Create Organization
                </Button>
              </CardContent>
            </Card>
          ) : (
            organizations.map((org: any) => (
              <Card key={org.id}>
                <CardHeader>
                  <div className="flex items-start justify-between">
                    <div>
                      <CardTitle>{org.name}</CardTitle>
                      <CardDescription className="font-mono text-xs">
                        {org.slug}
                      </CardDescription>
                    </div>
                    <Badge variant={org.is_active ? 'default' : 'secondary'}>
                      {org.is_active ? t('active') : t('inactive')}
                    </Badge>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="space-y-4">
                    <div className="text-sm">
                      <div className="text-muted-foreground">Contact Email</div>
                      <div>{org.contact_email || 'Not set'}</div>
                    </div>
                    <div className="text-sm">
                      <div className="text-muted-foreground">Rate Limit</div>
                      <div>{org.rate_limit_per_hour} requests/hour</div>
                    </div>
                    <div className="flex gap-2 pt-2">
                      <Button variant="outline" size="sm" className="flex-1" asChild>
                        <Link href={`/api-keys?org=${org.id}`}>
                          <Key className="mr-2 h-4 w-4" />
                          API Keys
                        </Link>
                      </Button>
                      <Button variant="outline" size="sm">
                        <Settings className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))
          )}
        </div>
      </div>
    </DashboardLayout>
  );
}

function CreateOrganizationForm({ onSuccess }: { onSuccess: () => void }) {
  const [formData, setFormData] = useState({
    name: '',
    slug: '',
    contact_email: '',
    rate_limit_per_hour: '1000',
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await organizationsApi.create(formData, 'admin-user-id');
      onSuccess();
    } catch (error) {
      console.error('Failed to create organization:', error);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <Label htmlFor="name">Organization Name</Label>
        <Input
          id="name"
          value={formData.name}
          onChange={(e) => setFormData({ ...formData, name: e.target.value })}
          required
        />
      </div>
      <div>
        <Label htmlFor="slug">Slug (URL-friendly identifier)</Label>
        <Input
          id="slug"
          value={formData.slug}
          onChange={(e) => setFormData({ ...formData, slug: e.target.value.toLowerCase().replace(/\s+/g, '-') })}
          required
          pattern="[a-z0-9-]+"
        />
        <p className="text-xs text-muted-foreground mt-1">
          Lowercase letters, numbers, and hyphens only
        </p>
      </div>
      <div>
        <Label htmlFor="email">Contact Email</Label>
        <Input
          id="email"
          type="email"
          value={formData.contact_email}
          onChange={(e) => setFormData({ ...formData, contact_email: e.target.value })}
        />
      </div>
      <div>
        <Label htmlFor="rate_limit">Rate Limit (requests per hour)</Label>
        <Input
          id="rate_limit"
          type="number"
          value={formData.rate_limit_per_hour}
          onChange={(e) => setFormData({ ...formData, rate_limit_per_hour: e.target.value })}
          min="1"
          max="100000"
        />
      </div>
      <DialogFooter>
        <Button type="button" variant="outline" onClick={onSuccess}>
          Cancel
        </Button>
        <Button type="submit">Create Organization</Button>
      </DialogFooter>
    </form>
  );
}

