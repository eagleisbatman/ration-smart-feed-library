'use client';

import { useState } from 'react';
import { DashboardLayout } from '@/components/layout/dashboard-layout';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { organizationsApi, apiKeysApi, auth } from '@/lib/api';
import { toast } from 'sonner';
import { Plus, Key, Building2, Copy, Trash2, Eye, EyeOff, Loader2 } from 'lucide-react';
import { ProtectedRoute } from '@/components/auth/protected-route';

function APIKeysContent() {
  const queryClient = useQueryClient();
  const user = auth.getCurrentUser();
  const [selectedOrg, setSelectedOrg] = useState<string>('');
  const [isGenerateDialogOpen, setIsGenerateDialogOpen] = useState(false);
  const [newKey, setNewKey] = useState<string | null>(null);
  const [keyName, setKeyName] = useState('');
  const [revokingKeyId, setRevokingKeyId] = useState<string | null>(null);
  const [visibleKeys, setVisibleKeys] = useState<Set<string>>(new Set());

  // Fetch organizations
  const { data: organizations = [] } = useQuery({
    queryKey: ['organizations', user?.id],
    queryFn: () => {
      if (!user?.id) throw new Error('User not authenticated');
      return organizationsApi.getAll(user.id).then(res => res.data);
    },
    enabled: !!user?.id,
  });

  // Fetch API keys for selected organization
  const { data: apiKeys = [], isLoading: isLoadingKeys } = useQuery({
    queryKey: ['api-keys', selectedOrg, user?.id],
    queryFn: () => {
      if (!selectedOrg || !user?.id) throw new Error('Organization or user not selected');
      return apiKeysApi.getAll(selectedOrg, user.id).then(res => res.data);
    },
    enabled: !!selectedOrg && !!user?.id,
  });

  // Generate API key mutation
  const generateKeyMutation = useMutation({
    mutationFn: async ({ orgId, name }: { orgId: string; name: string }) => {
      if (!user?.id) throw new Error('User not authenticated');
      return apiKeysApi.create(orgId, { name }, user.id);
    },
    onSuccess: (data) => {
      setNewKey(data.data.api_key);
      setIsGenerateDialogOpen(true);
      queryClient.invalidateQueries({ queryKey: ['api-keys'] });
      toast.success('API Key Generated', {
        description: 'Copy the key now - it will not be shown again!',
      });
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to generate API key');
    },
  });

  // Revoke API key mutation
  const revokeKeyMutation = useMutation({
    mutationFn: async (keyId: string) => {
      if (!user?.id) throw new Error('User not authenticated');
      return apiKeysApi.revoke(keyId, user.id);
    },
    onSuccess: () => {
      toast.success('API key revoked successfully');
      queryClient.invalidateQueries({ queryKey: ['api-keys'] });
      setRevokingKeyId(null);
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to revoke API key');
    },
  });

  const handleGenerateKey = () => {
    if (!selectedOrg) {
      toast.error('Please select an organization');
      return;
    }
    if (!keyName.trim()) {
      toast.error('Please enter a name for the API key');
      return;
    }
    generateKeyMutation.mutate({ orgId: selectedOrg, name: keyName });
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    toast.success('API key copied to clipboard');
  };

  const toggleKeyVisibility = (keyId: string) => {
    setVisibleKeys(prev => {
      const next = new Set(prev);
      if (next.has(keyId)) {
        next.delete(keyId);
      } else {
        next.add(keyId);
      }
      return next;
    });
  };

  return (
    <DashboardLayout>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold tracking-tight flex items-center gap-2">
              <Key className="h-8 w-8" />
              API Key Management
            </h1>
            <p className="text-muted-foreground">
              Generate and manage API keys for organizations
            </p>
          </div>
          <Button asChild>
            <a href="/organizations">
              <Building2 className="mr-2 h-4 w-4" />
              Manage Organizations
            </a>
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
              <Select value={selectedOrg} onValueChange={setSelectedOrg}>
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="Select an organization" />
                </SelectTrigger>
                <SelectContent>
                  {organizations.map((org: any) => (
                    <SelectItem key={org.id} value={org.id}>
                      {org.name} ({org.slug})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {selectedOrg && (
                <Dialog open={isGenerateDialogOpen} onOpenChange={setIsGenerateDialogOpen}>
                  <DialogTrigger asChild>
                    <Button>
                      <Plus className="mr-2 h-4 w-4" />
                      Generate API Key
                    </Button>
                  </DialogTrigger>
                  <DialogContent>
                    <DialogHeader>
                      <DialogTitle>Generate New API Key</DialogTitle>
                      <DialogDescription>
                        Create a new API key for {organizations.find((o: any) => o.id === selectedOrg)?.name}
                      </DialogDescription>
                    </DialogHeader>
                    {newKey ? (
                      <div className="space-y-4 py-4">
                        <div className="p-4 bg-muted rounded-lg">
                          <Label className="text-sm text-muted-foreground">API Key (Copy this now - it won't be shown again)</Label>
                          <div className="flex items-center gap-2 mt-2">
                            <Input
                              value={newKey}
                              readOnly
                              className="font-mono text-sm"
                            />
                            <Button
                              variant="outline"
                              size="icon"
                              onClick={() => copyToClipboard(newKey)}
                            >
                              <Copy className="h-4 w-4" />
                            </Button>
                          </div>
                        </div>
                        <div className="p-4 border border-yellow-500 rounded-lg bg-yellow-50 dark:bg-yellow-900/20">
                          <p className="text-sm text-yellow-800 dark:text-yellow-200">
                            ⚠️ Important: Save this API key securely. You won't be able to see it again.
                          </p>
                        </div>
                      </div>
                    ) : (
                      <div className="space-y-4 py-4">
                        <div className="space-y-2">
                          <Label htmlFor="key-name">Key Name</Label>
                          <Input
                            id="key-name"
                            value={keyName}
                            onChange={(e) => setKeyName(e.target.value)}
                            placeholder="Production API Key"
                          />
                          <p className="text-xs text-muted-foreground">
                            A friendly name to identify this API key
                          </p>
                        </div>
                      </div>
                    )}
                    <DialogFooter>
                      <Button
                        variant="outline"
                        onClick={() => {
                          setIsGenerateDialogOpen(false);
                          setNewKey(null);
                          setKeyName('');
                        }}
                      >
                        {newKey ? 'Close' : 'Cancel'}
                      </Button>
                      {!newKey && (
                        <Button
                          onClick={handleGenerateKey}
                          disabled={generateKeyMutation.isPending || !keyName.trim()}
                        >
                          {generateKeyMutation.isPending ? (
                            <>
                              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                              Generating...
                            </>
                          ) : (
                            'Generate'
                          )}
                        </Button>
                      )}
                    </DialogFooter>
                  </DialogContent>
                </Dialog>
              )}
            </div>
          </CardContent>
        </Card>

        {/* API Keys Table */}
        {selectedOrg && (
          <Card>
            <CardHeader>
              <CardTitle>API Keys</CardTitle>
              <CardDescription>
                Manage API keys for {organizations.find((o: any) => o.id === selectedOrg)?.name}
              </CardDescription>
            </CardHeader>
            <CardContent>
              {isLoadingKeys ? (
                <div className="text-center py-8">
                  <Loader2 className="h-8 w-8 animate-spin mx-auto mb-4" />
                  <p className="text-muted-foreground">Loading API keys...</p>
                </div>
              ) : apiKeys.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  No API keys found. Generate one to get started.
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
                        <TableCell className="font-medium">{key.name || 'Unnamed'}</TableCell>
                        <TableCell className="font-mono text-sm">
                          {visibleKeys.has(key.id) ? (
                            <span className="text-muted-foreground">Full key hidden</span>
                          ) : (
                            `${key.key_prefix}...`
                          )}
                        </TableCell>
                        <TableCell>
                          <Badge variant={key.is_active ? 'default' : 'secondary'}>
                            {key.is_active ? 'Active' : 'Revoked'}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          {key.last_used_at 
                            ? new Date(key.last_used_at).toLocaleDateString()
                            : 'Never'
                          }
                        </TableCell>
                        <TableCell>
                          {key.expires_at
                            ? new Date(key.expires_at).toLocaleDateString()
                            : 'Never'
                          }
                        </TableCell>
                        <TableCell className="text-right">
                          <div className="flex justify-end gap-2">
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={() => toggleKeyVisibility(key.id)}
                            >
                              {visibleKeys.has(key.id) ? (
                                <EyeOff className="h-4 w-4" />
                              ) : (
                                <Eye className="h-4 w-4" />
                              )}
                            </Button>
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={() => setRevokingKeyId(key.id)}
                              disabled={!key.is_active}
                            >
                              <Trash2 className="h-4 w-4 text-destructive" />
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

        {/* Revoke Confirmation Dialog */}
        <AlertDialog open={!!revokingKeyId} onOpenChange={(open) => !open && setRevokingKeyId(null)}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Revoke API Key?</AlertDialogTitle>
              <AlertDialogDescription>
                This action cannot be undone. The API key will be immediately deactivated and all requests using it will fail.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel disabled={revokeKeyMutation.isPending}>Cancel</AlertDialogCancel>
              <AlertDialogAction
                onClick={() => {
                  if (revokingKeyId) {
                    revokeKeyMutation.mutate(revokingKeyId);
                  }
                }}
                disabled={revokeKeyMutation.isPending}
                className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              >
                {revokeKeyMutation.isPending ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Revoking...
                  </>
                ) : (
                  'Revoke'
                )}
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </div>
    </DashboardLayout>
  );
}

export default function APIKeysPage() {
  return (
    <ProtectedRoute allowedRoles={['admin', 'superadmin', 'organization_admin']}>
      <APIKeysContent />
    </ProtectedRoute>
  );
}
