'use client';

import { useState, useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Button } from '@/components/ui/button';
import { Loader2, Plus, Trash2, Globe } from 'lucide-react';
import { toast } from 'sonner';
import { feedsApi, countriesApi, countryAdminFeedsApi } from '@/lib/api';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { auth } from '@/lib/auth';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Badge } from '@/components/ui/badge';
import { FeedTranslationsTab } from './feed-translations-tab';

const feedSchema = z.object({
  fd_code: z.string().min(1, 'Feed code is required'),
  fd_name_default: z.string().min(1, 'Feed name is required'),
  fd_type: z.enum(['Forage', 'Concentrate'], { required_error: 'Feed type is required' }),
  fd_category: z.string().optional(),
  fd_country_id: z.string().min(1, 'Country is required'),
  // Nutritional values
  fd_dm: z.number().optional(),
  fd_ash: z.number().optional(),
  fd_cp: z.number().optional(),
  fd_ee: z.number().optional(),
  fd_st: z.number().optional(),
  fd_ndf: z.number().optional(),
  fd_adf: z.number().optional(),
  fd_lg: z.number().optional(),
  fd_ca: z.number().optional(),
  fd_p: z.number().optional(),
  fd_cf: z.number().optional(),
  fd_nfe: z.number().optional(),
  fd_hemicellulose: z.number().optional(),
  fd_cellulose: z.number().optional(),
  fd_ndin: z.number().optional(),
  fd_adin: z.number().optional(),
  fd_npn_cp: z.number().int().optional(),
  // Metadata
  fd_season: z.string().optional(),
  fd_orginin: z.string().optional(),
  fd_ipb_local_lab: z.string().optional(),
});

type FeedFormValues = z.infer<typeof feedSchema>;

interface FeedFormProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  feedId?: string;
  countryId?: string; // For country admin - pre-fill country
}

export function FeedForm({ open, onOpenChange, feedId, countryId }: FeedFormProps) {
  const queryClient = useQueryClient();
  const user = auth.getCurrentUser();
  const isEdit = !!feedId;

  // Fetch countries
  const { data: countries = [] } = useQuery({
    queryKey: ['countries'],
    queryFn: () => countriesApi.getAll().then(res => res.data),
  });

  // Fetch feed if editing
  const { data: feedData } = useQuery({
    queryKey: ['feed', feedId],
    queryFn: () => feedsApi.getById(feedId!).then(res => res.data),
    enabled: isEdit && !!feedId,
  });

  const form = useForm<FeedFormValues>({
    resolver: zodResolver(feedSchema),
    defaultValues: {
      fd_code: '',
      fd_name_default: '',
      fd_type: 'Forage',
      fd_category: '',
      fd_country_id: countryId || '',
      fd_dm: undefined,
      fd_ash: undefined,
      fd_cp: undefined,
      fd_ee: undefined,
      fd_st: undefined,
      fd_ndf: undefined,
      fd_adf: undefined,
      fd_lg: undefined,
      fd_ca: undefined,
      fd_p: undefined,
      fd_cf: undefined,
      fd_nfe: undefined,
      fd_hemicellulose: undefined,
      fd_cellulose: undefined,
      fd_ndin: undefined,
      fd_adin: undefined,
      fd_npn_cp: undefined,
      fd_season: '',
      fd_orginin: '',
      fd_ipb_local_lab: '',
    },
  });

  // Populate form when feed data loads
  useEffect(() => {
    if (feedData && isEdit) {
      form.reset({
        fd_code: feedData.fd_code || '',
        fd_name_default: feedData.fd_name_default || feedData.fd_name || '',
        fd_type: feedData.fd_type || 'Forage',
        fd_category: feedData.fd_category || '',
        fd_country_id: feedData.fd_country_id || '',
        fd_dm: feedData.fd_dm ? parseFloat(feedData.fd_dm) : undefined,
        fd_ash: feedData.fd_ash ? parseFloat(feedData.fd_ash) : undefined,
        fd_cp: feedData.fd_cp ? parseFloat(feedData.fd_cp) : undefined,
        fd_ee: feedData.fd_ee ? parseFloat(feedData.fd_ee) : undefined,
        fd_st: feedData.fd_st ? parseFloat(feedData.fd_st) : undefined,
        fd_ndf: feedData.fd_ndf ? parseFloat(feedData.fd_ndf) : undefined,
        fd_adf: feedData.fd_adf ? parseFloat(feedData.fd_adf) : undefined,
        fd_lg: feedData.fd_lg ? parseFloat(feedData.fd_lg) : undefined,
        fd_ca: feedData.fd_ca ? parseFloat(feedData.fd_ca) : undefined,
        fd_p: feedData.fd_p ? parseFloat(feedData.fd_p) : undefined,
        fd_cf: feedData.fd_cf ? parseFloat(feedData.fd_cf) : undefined,
        fd_nfe: feedData.fd_nfe ? parseFloat(feedData.fd_nfe) : undefined,
        fd_hemicellulose: feedData.fd_hemicellulose ? parseFloat(feedData.fd_hemicellulose) : undefined,
        fd_cellulose: feedData.fd_cellulose ? parseFloat(feedData.fd_cellulose) : undefined,
        fd_ndin: feedData.fd_ndin ? parseFloat(feedData.fd_ndin) : undefined,
        fd_adin: feedData.fd_adin ? parseFloat(feedData.fd_adin) : undefined,
        fd_npn_cp: feedData.fd_npn_cp ? parseInt(feedData.fd_npn_cp) : undefined,
        fd_season: feedData.fd_season || '',
        fd_orginin: feedData.fd_orginin || '',
        fd_ipb_local_lab: feedData.fd_ipb_local_lab || '',
      });
    }
  }, [feedData, isEdit, form]);

  // Set country if provided (for country admin)
  useEffect(() => {
    if (countryId && !isEdit) {
      form.setValue('fd_country_id', countryId);
    }
  }, [countryId, isEdit, form]);

  const createMutation = useMutation({
    mutationFn: (data: FeedFormValues) => {
      if (!user?.id && !user?.email_id) throw new Error('User not authenticated');
      
      // Find country name
      const country = countries.find((c: any) => c.id === data.fd_country_id);
      if (!country) throw new Error('Country not found');

      const payload = {
        ...data,
        fd_name: data.fd_name_default, // Legacy field
        fd_country_name: country.name,
        fd_country_cd: country.country_code,
      };

      // Use country admin API if user is country admin
      if (user?.country_admin_country_id && user?.email_id) {
        return countryAdminFeedsApi.createFeed(user.email_id, payload);
      }

      // Otherwise use admin API
      return feedsApi.create(payload, user.id);
    },
    onSuccess: () => {
      toast.success('Feed created successfully');
      queryClient.invalidateQueries({ queryKey: ['feeds'] });
      queryClient.invalidateQueries({ queryKey: ['country-feeds'] });
      form.reset();
      onOpenChange(false);
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to create feed');
    },
  });

  const updateMutation = useMutation({
    mutationFn: (data: FeedFormValues) => {
      if ((!user?.id && !user?.email_id) || !feedId) throw new Error('User not authenticated or feed ID missing');
      
      const country = countries.find((c: any) => c.id === data.fd_country_id);
      if (!country) throw new Error('Country not found');

      const payload = {
        ...data,
        fd_name: data.fd_name_default,
        fd_country_name: country.name,
        fd_country_cd: country.country_code,
      };

      // Use country admin API if user is country admin
      if (user?.country_admin_country_id && user?.email_id) {
        return countryAdminFeedsApi.updateFeed(user.email_id, feedId, payload);
      }

      // Otherwise use admin API
      return feedsApi.update(feedId, payload, user.id);
    },
    onSuccess: () => {
      toast.success('Feed updated successfully');
      queryClient.invalidateQueries({ queryKey: ['feeds'] });
      queryClient.invalidateQueries({ queryKey: ['feed', feedId] });
      queryClient.invalidateQueries({ queryKey: ['country-feeds'] });
      onOpenChange(false);
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to update feed');
    },
  });

  const onSubmit = (data: FeedFormValues) => {
    if (isEdit) {
      updateMutation.mutate(data);
    } else {
      createMutation.mutate(data);
    }
  };

  const isLoading = createMutation.isPending || updateMutation.isPending;
  const user = auth.getCurrentUser();
  const userEmail = user?.email_id || '';

  // Fetch translations if editing
  const { data: translationsData } = useQuery({
    queryKey: ['feed-translations', feedId, userEmail],
    queryFn: () => {
      if (!feedId || !userEmail) throw new Error('Feed ID or user email missing');
      return countryAdminFeedsApi.getTranslations(userEmail, feedId).then(res => res.data);
    },
    enabled: isEdit && !!feedId && !!userEmail && !!user?.country_admin_country_id,
  });

  const translations = translationsData?.translations || [];

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{isEdit ? 'Edit Feed' : 'Create New Feed'}</DialogTitle>
          <DialogDescription>
            {isEdit 
              ? 'Update feed information, nutritional values, and translations'
              : 'Add a new feed to the database with nutritional information'
            }
          </DialogDescription>
        </DialogHeader>

        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
            <Tabs defaultValue="basic" className="w-full">
              <TabsList className="grid w-full grid-cols-3">
                <TabsTrigger value="basic">Basic Info</TabsTrigger>
                <TabsTrigger value="nutritional">Nutritional Values</TabsTrigger>
                <TabsTrigger value="translations">
                  Translations
                  {translations.length > 0 && (
                    <Badge variant="secondary" className="ml-2">
                      {translations.length}
                    </Badge>
                  )}
                </TabsTrigger>
              </TabsList>

              <TabsContent value="basic" className="space-y-4">
            {/* Basic Information */}
            <div className="grid grid-cols-2 gap-4">
              <FormField
                control={form.control}
                name="fd_code"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Feed Code</FormLabel>
                    <FormControl>
                      <Input placeholder="ETH-001" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="fd_name_default"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Feed Name (English)</FormLabel>
                    <FormControl>
                      <Input placeholder="Corn Silage" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="fd_type"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Feed Type</FormLabel>
                    <Select onValueChange={field.onChange} defaultValue={field.value}>
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue placeholder="Select feed type" />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        <SelectItem value="Forage">Forage</SelectItem>
                        <SelectItem value="Concentrate">Concentrate</SelectItem>
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="fd_category"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Category</FormLabel>
                    <FormControl>
                      <Input placeholder="Grass" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="fd_country_id"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Country</FormLabel>
                    <Select 
                      onValueChange={field.onChange} 
                      defaultValue={field.value}
                      disabled={!!countryId}
                    >
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue placeholder="Select country" />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {countries.map((country: any) => (
                          <SelectItem key={country.id} value={country.id}>
                            {country.name} ({country.country_code})
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>


                {/* Metadata */}
                <div className="grid grid-cols-3 gap-4">
                  <FormField
                    control={form.control}
                    name="fd_season"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Season</FormLabel>
                        <FormControl>
                          <Input placeholder="Dry/Wet" {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <FormField
                    control={form.control}
                    name="fd_orginin"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Origin</FormLabel>
                        <FormControl>
                          <Input placeholder="Origin" {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <FormField
                    control={form.control}
                    name="fd_ipb_local_lab"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Lab Reference</FormLabel>
                        <FormControl>
                          <Input placeholder="Lab reference" {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </div>
              </TabsContent>

              <TabsContent value="nutritional" className="space-y-4">
                {/* Nutritional Values */}
                <div className="space-y-4">
                  <h3 className="text-lg font-semibold">Nutritional Values (%)</h3>
                  <div className="grid grid-cols-3 gap-4">
                    {[
                      { name: 'fd_dm', label: 'Dry Matter (DM)' },
                      { name: 'fd_ash', label: 'Ash' },
                      { name: 'fd_cp', label: 'Crude Protein (CP)' },
                      { name: 'fd_ee', label: 'Ether Extract (EE)' },
                      { name: 'fd_st', label: 'Starch (ST)' },
                      { name: 'fd_ndf', label: 'NDF' },
                      { name: 'fd_adf', label: 'ADF' },
                      { name: 'fd_lg', label: 'Lignin (LG)' },
                      { name: 'fd_ca', label: 'Calcium (Ca)' },
                      { name: 'fd_p', label: 'Phosphorus (P)' },
                      { name: 'fd_cf', label: 'Crude Fiber (CF)' },
                      { name: 'fd_nfe', label: 'NFE' },
                      { name: 'fd_hemicellulose', label: 'Hemicellulose' },
                      { name: 'fd_cellulose', label: 'Cellulose' },
                      { name: 'fd_ndin', label: 'NDIN' },
                      { name: 'fd_adin', label: 'ADIN' },
                    ].map((field) => (
                      <FormField
                        key={field.name}
                        control={form.control}
                        name={field.name as keyof FeedFormValues}
                        render={({ field: formField }) => (
                          <FormItem>
                            <FormLabel>{field.label}</FormLabel>
                            <FormControl>
                              <Input
                                type="number"
                                step="0.01"
                                placeholder="0.00"
                                {...formField}
                                value={formField.value ?? ''}
                                onChange={(e) => {
                                  const value = e.target.value;
                                  formField.onChange(value === '' ? undefined : parseFloat(value));
                                }}
                              />
                            </FormControl>
                            <FormMessage />
                          </FormItem>
                        )}
                      />
                    ))}
                  </div>

                  <FormField
                    control={form.control}
                    name="fd_npn_cp"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>NPN-CP (Integer)</FormLabel>
                        <FormControl>
                          <Input
                            type="number"
                            step="1"
                            placeholder="0"
                            {...field}
                            value={field.value ?? ''}
                            onChange={(e) => {
                              const value = e.target.value;
                              field.onChange(value === '' ? undefined : parseInt(value));
                            }}
                          />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </div>
              </TabsContent>

              <TabsContent value="translations" className="space-y-4">
                <FeedTranslationsTab 
                  feedId={feedId} 
                  feedName={form.watch('fd_name_default')}
                  countryId={form.watch('fd_country_id')}
                  translations={translations}
                  userEmail={userEmail}
                  isEdit={isEdit}
                />
              </TabsContent>
            </Tabs>

            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => onOpenChange(false)}
                disabled={isLoading}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={isLoading}>
                {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                {isEdit ? 'Update Feed' : 'Create Feed'}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}

