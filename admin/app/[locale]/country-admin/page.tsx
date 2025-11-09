'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { DashboardLayout } from '@/components/layout/dashboard-layout';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
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
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { countryAdminFeedsApi, auth } from '@/lib/api';
import { toast } from 'sonner';
import { Globe, Database, Upload, Plus, Search, Filter, Edit, Trash2, Loader2, X } from 'lucide-react';
import { FeedForm } from '@/components/feeds/feed-form';
import { ProtectedRoute } from '@/components/auth/protected-route';

function CountryAdminContent() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const user = auth.getCurrentUser();
  const userEmail = user?.email_id || '';
  
  const [searchQuery, setSearchQuery] = useState('');
  const [feedTypeFilter, setFeedTypeFilter] = useState<string>('all');
  const [isAddDialogOpen, setIsAddDialogOpen] = useState(false);
  const [isBulkUploadDialogOpen, setIsBulkUploadDialogOpen] = useState(false);
  const [editingFeedId, setEditingFeedId] = useState<string | null>(null);
  const [deletingFeedId, setDeletingFeedId] = useState<string | null>(null);
  const [uploadFile, setUploadFile] = useState<File | null>(null);

  // Fetch assigned country
  const { data: myCountry, isLoading: isLoadingCountry } = useQuery({
    queryKey: ['my-country', userEmail],
    queryFn: () => countryAdminFeedsApi.getMyCountry(userEmail).then(res => res.data),
    enabled: !!userEmail,
  });

  const countryId = myCountry?.country?.id;

  // Fetch feeds for assigned country
  const { data: feedsData, isLoading: isLoadingFeeds } = useQuery({
    queryKey: ['country-feeds', userEmail, feedTypeFilter, searchQuery],
    queryFn: () => countryAdminFeedsApi.getFeeds(userEmail, {
      feed_type: feedTypeFilter !== 'all' ? feedTypeFilter : undefined,
      search: searchQuery || undefined,
      limit: 1000,
    }).then(res => res.data),
    enabled: !!userEmail,
  });

  const feeds = feedsData?.feeds || [];
  const filteredFeeds = feeds.filter((feed: any) =>
    feed.fd_name_default?.toLowerCase().includes(searchQuery.toLowerCase()) ||
    feed.fd_code?.toLowerCase().includes(searchQuery.toLowerCase())
  );

  // Bulk upload mutation
  const bulkUploadMutation = useMutation({
    mutationFn: async (file: File) => {
      if (!userEmail) throw new Error('User not authenticated');
      return countryAdminFeedsApi.bulkUpload(userEmail, file);
    },
    onSuccess: () => {
      toast.success('Bulk upload completed successfully');
      queryClient.invalidateQueries({ queryKey: ['country-feeds'] });
      setIsBulkUploadDialogOpen(false);
      setUploadFile(null);
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Bulk upload failed');
    },
  });

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: async (feedId: string) => {
      if (!userEmail) throw new Error('User not authenticated');
      // Country admin can use admin delete endpoint since they have is_admin=True
      // The backend will verify the feed belongs to their country
      const { feedsApi } = await import('@/lib/api');
      const user = auth.getCurrentUser();
      if (!user?.id) throw new Error('User not authenticated');
      return feedsApi.delete(feedId, user.id);
    },
    onSuccess: () => {
      toast.success('Feed deleted successfully');
      queryClient.invalidateQueries({ queryKey: ['country-feeds'] });
      setDeletingFeedId(null);
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to delete feed');
    },
  });

  const handleBulkUpload = () => {
    if (!uploadFile) {
      toast.error('Please select a file');
      return;
    }
    bulkUploadMutation.mutate(uploadFile);
  };

  const handleDelete = (feedId: string) => {
    setDeletingFeedId(feedId);
  };

  const confirmDelete = () => {
    if (deletingFeedId) {
      deleteMutation.mutate(deletingFeedId);
    }
  };

  if (!userEmail) {
    router.push('/login');
    return null;
  }

  return (
    <DashboardLayout>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold tracking-tight flex items-center gap-2">
              <Globe className="h-8 w-8" />
              Country Admin Dashboard
            </h1>
            <p className="text-muted-foreground">
              {isLoadingCountry ? (
                'Loading your assigned country...'
              ) : myCountry?.country ? (
                <>
                  Managing feeds for <strong>{myCountry.country.name}</strong> ({myCountry.country.country_code})
                </>
              ) : (
                'No country assigned'
              )}
            </p>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => setIsBulkUploadDialogOpen(true)}>
              <Upload className="mr-2 h-4 w-4" />
              Bulk Upload
            </Button>
            <Button onClick={() => setIsAddDialogOpen(true)}>
              <Plus className="mr-2 h-4 w-4" />
              Add Feed
            </Button>
          </div>
        </div>

        {/* Country Info Card */}
        {myCountry?.country && (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Globe className="h-5 w-5" />
                Assigned Country
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-3 gap-4">
                <div>
                  <p className="text-sm text-muted-foreground">Country Name</p>
                  <p className="text-lg font-semibold">{myCountry.country.name}</p>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Country Code</p>
                  <p className="text-lg font-semibold">{myCountry.country.country_code}</p>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Currency</p>
                  <p className="text-lg font-semibold">{myCountry.country.currency || 'N/A'}</p>
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Stats */}
        <div className="grid gap-4 md:grid-cols-3">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Total Feeds</CardTitle>
              <Database className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{feedsData?.total || 0}</div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Forage Feeds</CardTitle>
              <Filter className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {feeds.filter((f: any) => f.fd_type === 'Forage').length}
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Concentrate Feeds</CardTitle>
              <Filter className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {feeds.filter((f: any) => f.fd_type === 'Concentrate').length}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Feeds Table */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>Feeds</CardTitle>
                <CardDescription>
                  Manage feeds for your assigned country
                </CardDescription>
              </div>
              <div className="flex gap-2">
                <div className="relative">
                  <Search className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
                  <Input
                    placeholder="Search feeds..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="pl-10 w-64"
                  />
                </div>
                <select
                  value={feedTypeFilter}
                  onChange={(e) => setFeedTypeFilter(e.target.value)}
                  className="px-3 py-2 border rounded-md bg-background"
                >
                  <option value="all">All Types</option>
                  <option value="Forage">Forage</option>
                  <option value="Concentrate">Concentrate</option>
                </select>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            {isLoadingFeeds ? (
              <div className="text-center py-8">
                <Loader2 className="h-8 w-8 animate-spin mx-auto mb-4" />
                <p className="text-muted-foreground">Loading feeds...</p>
              </div>
            ) : filteredFeeds.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                {searchQuery ? 'No feeds match your search' : 'No feeds found. Add your first feed to get started.'}
              </div>
            ) : (
              <div className="rounded-md border">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Code</TableHead>
                      <TableHead>Name</TableHead>
                      <TableHead>Type</TableHead>
                      <TableHead>Category</TableHead>
                      <TableHead>DM %</TableHead>
                      <TableHead>CP %</TableHead>
                      <TableHead>NDF %</TableHead>
                      <TableHead className="text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {filteredFeeds.map((feed: any) => (
                      <TableRow key={feed.id}>
                        <TableCell className="font-mono text-sm">{feed.fd_code}</TableCell>
                        <TableCell className="font-medium">{feed.fd_name_default}</TableCell>
                        <TableCell>
                          <Badge variant={feed.fd_type === 'Forage' ? 'default' : 'secondary'}>
                            {feed.fd_type}
                          </Badge>
                        </TableCell>
                        <TableCell>{feed.fd_category || 'N/A'}</TableCell>
                        <TableCell>{feed.fd_dm?.toFixed(2) || 'N/A'}</TableCell>
                        <TableCell>{feed.fd_cp?.toFixed(2) || 'N/A'}</TableCell>
                        <TableCell>{feed.fd_ndf?.toFixed(2) || 'N/A'}</TableCell>
                        <TableCell className="text-right">
                          <div className="flex justify-end gap-2">
                            <Button 
                              variant="ghost" 
                              size="icon"
                              onClick={() => setEditingFeedId(feed.id)}
                            >
                              <Edit className="h-4 w-4" />
                            </Button>
                            <Button 
                              variant="ghost" 
                              size="icon"
                              onClick={() => handleDelete(feed.id)}
                            >
                              <Trash2 className="h-4 w-4 text-destructive" />
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Add Feed Dialog */}
        <FeedForm
          open={isAddDialogOpen}
          onOpenChange={setIsAddDialogOpen}
          countryId={countryId}
        />

        {/* Edit Feed Dialog */}
        {editingFeedId && (
          <FeedForm
            open={!!editingFeedId}
            onOpenChange={(open) => {
              if (!open) setEditingFeedId(null);
            }}
            feedId={editingFeedId}
            countryId={countryId}
          />
        )}

        {/* Bulk Upload Dialog */}
        <Dialog open={isBulkUploadDialogOpen} onOpenChange={setIsBulkUploadDialogOpen}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Bulk Upload Feeds</DialogTitle>
              <DialogDescription>
                Upload an Excel file (.xls or .xlsx) to import multiple feeds at once
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div className="border-2 border-dashed rounded-lg p-6 text-center">
                <Upload className="h-12 w-12 mx-auto mb-4 text-muted-foreground" />
                <input
                  type="file"
                  accept=".xls,.xlsx"
                  onChange={(e) => setUploadFile(e.target.files?.[0] || null)}
                  className="hidden"
                  id="file-upload"
                />
                <label htmlFor="file-upload" className="cursor-pointer">
                  <Button variant="outline" as="span">
                    Select File
                  </Button>
                </label>
                {uploadFile && (
                  <div className="mt-4 flex items-center justify-center gap-2">
                    <span className="text-sm">{uploadFile.name}</span>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => setUploadFile(null)}
                    >
                      <X className="h-4 w-4" />
                    </Button>
                  </div>
                )}
              </div>
            </div>
            <DialogFooter>
              <Button
                variant="outline"
                onClick={() => {
                  setIsBulkUploadDialogOpen(false);
                  setUploadFile(null);
                }}
                disabled={bulkUploadMutation.isPending}
              >
                Cancel
              </Button>
              <Button
                onClick={handleBulkUpload}
                disabled={!uploadFile || bulkUploadMutation.isPending}
              >
                {bulkUploadMutation.isPending ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Uploading...
                  </>
                ) : (
                  'Upload'
                )}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Delete Confirmation Dialog */}
        <AlertDialog open={!!deletingFeedId} onOpenChange={(open) => !open && setDeletingFeedId(null)}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Are you sure?</AlertDialogTitle>
              <AlertDialogDescription>
                This action cannot be undone. This will permanently delete the feed from the database.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel disabled={deleteMutation.isPending}>Cancel</AlertDialogCancel>
              <AlertDialogAction
                onClick={confirmDelete}
                disabled={deleteMutation.isPending}
                className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              >
                {deleteMutation.isPending ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Deleting...
                  </>
                ) : (
                  'Delete'
                )}
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </div>
    </DashboardLayout>
  );
}

export default function CountryAdminPage() {
  return (
    <ProtectedRoute allowedRoles={['country_admin', 'superadmin']}>
      <CountryAdminContent />
    </ProtectedRoute>
  );
}
