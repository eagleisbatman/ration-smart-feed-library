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
import { Link } from '@/lib/navigation';
import { useQuery } from '@tanstack/react-query';
import { organizationsApi, apiKeysApi } from '@/lib/api';
import { useState } from 'react';
import { Plus, Key, Building2, Copy, Trash2, Eye, EyeOff } from 'lucide-react';
import { toast } from 'sonner';

export default function APIKeysPage() {
  const t = useTranslations('apiKeys');
  const tCommon = useTranslations('common');
  const [selectedOrg, setSelectedOrg] = useState<string>('');
  const [isGenerateDialogOpen, setIsGenerateDialogOpen] = useState(false);
  const [newKey, setNewKey] = useState<string | null>(null);

  // Fetch organizations
  const { data: organizations = [] } = useQuery({
    queryKey: ['organizations'],
    queryFn: () => organizationsApi.getAll('admin-user-id').then(res => res.data),
  });

  // Fetch API keys for selected organization
  const { data: apiKeys = [], refetch } = useQuery({
    queryKey: ['api-keys', selectedOrg],
    queryFn: () => apiKeysApi.getAll(selectedOrg, 'admin-user-id').then(res => res.data),
    enabled: !!selectedOrg,
  });

  const handleGenerateKey = async (orgId: string, name: string) => {
    try {
      const response = await apiKeysApi.create(orgId, { name }, 'admin-user-id');
      setNewKey(response.data.api_key);
      setIsGenerateDialogOpen(true);
      refetch();
      toast.success('API Key Generated', {
        description: 'Copy the key now - it will not be shown again!',
      });
    } catch (error) {
      toast.error('Failed to generate API key');
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    toast.success('API key copied to clipboard');
  };

  return (
    <DashboardLayout>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">{t('title')}</h1>
            <p className="text-muted-foreground">
              Manage API keys for organizations using the Feed Formulation API
            </p>
          </div>
          <Button asChild>
            <Link href="/organizations">
              <Building2 className="mr-2 h-4 w-4" />
              Manage Organizations
            </Link>
          </Button>
        </div>

        {/* Organization Selector */}
        <Card>
          <CardHeader>
            <CardTitle>Select Organization</CardTitle>
            <CardDescription>
              Choose an organization to view and manage its API keys
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex gap-4">
              <select
                value={selectedOrg}
                onChange={(e) => setSelectedOrg(e.target.value)}
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              >
                <option value="">Select an organization...</option>
                {organizations.map((org: any) => (
                  <option key={org.id} value={org.id}>
                    {org.name} ({org.slug})
                  </option>
                ))}
              </select>
            </div>
          </CardContent>
        </Card>

        {/* API Keys Table */}
        {selectedOrg && (
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>API Keys</CardTitle>
                  <CardDescription>
                    {apiKeys.length} API key{apiKeys.length !== 1 ? 's' : ''} for this organization
                  </CardDescription>
                </div>
                <Dialog>
                  <DialogTrigger asChild>
                    <Button>
                      <Plus className="mr-2 h-4 w-4" />
                      {t('generateKey')}
                    </Button>
                  </DialogTrigger>
                  <DialogContent>
                    <DialogHeader>
                      <DialogTitle>{t('generateKey')}</DialogTitle>
                      <DialogDescription>
                        Generate a new API key for this organization
                      </DialogDescription>
                    </DialogHeader>
                    <GenerateKeyForm
                      organizationId={selectedOrg}
                      onGenerate={handleGenerateKey}
                      onClose={() => setIsGenerateDialogOpen(false)}
                    />
                  </DialogContent>
                </Dialog>
              </div>
            </CardHeader>
            <CardContent>
              {apiKeys.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  No API keys found. Generate your first API key to get started.
                </div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Name</TableHead>
                      <TableHead>Key Prefix</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Last Used</TableHead>
                      <TableHead>Expires</TableHead>
                      <TableHead className="text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {apiKeys.map((key: any) => (
                      <TableRow key={key.id}>
                        <TableCell className="font-medium">{key.name || 'Unnamed Key'}</TableCell>
                        <TableCell className="font-mono text-sm">
                          {key.key_prefix}...
                        </TableCell>
                        <TableCell>
                          <Badge variant={key.is_active ? 'default' : 'secondary'}>
                            {key.is_active ? t('active') : t('inactive')}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          {key.last_used_at
                            ? new Date(key.last_used_at).toLocaleDateString()
                            : 'Never'}
                        </TableCell>
                        <TableCell>
                          {key.expires_at
                            ? new Date(key.expires_at).toLocaleDateString()
                            : 'Never'}
                        </TableCell>
                        <TableCell className="text-right">
                          <div className="flex justify-end gap-2">
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={() => copyToClipboard(key.key_prefix)}
                            >
                              <Copy className="h-4 w-4" />
                            </Button>
                            <Button variant="ghost" size="icon">
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        )}

        {/* New Key Dialog */}
        {newKey && (
          <Dialog open={isGenerateDialogOpen} onOpenChange={setIsGenerateDialogOpen}>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>API Key Generated</DialogTitle>
                <DialogDescription>
                  {t('keyWarning')}
                </DialogDescription>
              </DialogHeader>
              <div className="space-y-4">
                <div>
                  <Label>Your API Key</Label>
                  <div className="flex gap-2 mt-2">
                    <Input
                      value={newKey}
                      readOnly
                      className="font-mono"
                    />
                    <Button
                      onClick={() => copyToClipboard(newKey)}
                      variant="outline"
                    >
                      <Copy className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
                <div className="bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-md p-4">
                  <p className="text-sm text-yellow-800 dark:text-yellow-200">
                    ⚠️ This key will not be shown again. Store it securely.
                  </p>
                </div>
              </div>
              <DialogFooter>
                <Button onClick={() => {
                  setNewKey(null);
                  setIsGenerateDialogOpen(false);
                }}>
                  I've Saved It
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        )}
      </div>
    </DashboardLayout>
  );
}

function GenerateKeyForm({
  organizationId,
  onGenerate,
  onClose,
}: {
  organizationId: string;
  onGenerate: (orgId: string, name: string) => void;
  onClose: () => void;
}) {
  const [name, setName] = useState('');
  const [expiresInDays, setExpiresInDays] = useState<string>('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onGenerate(organizationId, name || 'API Key');
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <Label htmlFor="name">Key Name (Optional)</Label>
        <Input
          id="name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="e.g., Production API Key"
        />
      </div>
      <div>
        <Label htmlFor="expires">Expires In (Days, Optional)</Label>
        <Input
          id="expires"
          type="number"
          value={expiresInDays}
          onChange={(e) => setExpiresInDays(e.target.value)}
          placeholder="Leave empty for no expiration"
        />
      </div>
      <DialogFooter>
        <Button type="button" variant="outline" onClick={onClose}>
          Cancel
        </Button>
        <Button type="submit">Generate Key</Button>
      </DialogFooter>
    </form>
  );
}

