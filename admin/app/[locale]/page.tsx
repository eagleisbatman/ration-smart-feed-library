import { useTranslations } from 'next-intl';
import { DashboardLayout } from '@/components/layout/dashboard-layout';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Link } from '@/lib/navigation';
import { 
  Database, 
  Key, 
  Building2, 
  Globe,
  TrendingUp,
  Users
} from 'lucide-react';

export default function DashboardPage() {
  const t = useTranslations('common');

  const stats = [
    {
      title: 'Total Feeds',
      value: '1,234',
      icon: Database,
      change: '+12%',
      href: '/feeds',
    },
    {
      title: 'Organizations',
      value: '45',
      icon: Building2,
      change: '+5',
      href: '/organizations',
    },
    {
      title: 'API Keys',
      value: '128',
      icon: Key,
      change: '+8',
      href: '/api-keys',
    },
    {
      title: 'Countries',
      value: '12',
      icon: Globe,
      change: '+2',
      href: '/countries',
    },
  ];

  return (
    <DashboardLayout>
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">{t('dashboard')}</h1>
          <p className="text-muted-foreground">
            Welcome to the Feed Formulation Admin Dashboard
          </p>
        </div>

        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          {stats.map((stat) => {
            const Icon = stat.icon;
            return (
              <Card key={stat.title}>
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                  <CardTitle className="text-sm font-medium">{stat.title}</CardTitle>
                  <Icon className="h-4 w-4 text-muted-foreground" />
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold">{stat.value}</div>
                  <p className="text-xs text-muted-foreground">
                    <span className="text-green-600">{stat.change}</span> from last month
                  </p>
                  <Button variant="link" className="p-0 h-auto mt-2" asChild>
                    <Link href={stat.href}>View details →</Link>
                  </Button>
                </CardContent>
              </Card>
            );
          })}
        </div>

        <div className="grid gap-4 md:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle>Quick Actions</CardTitle>
              <CardDescription>Common tasks and shortcuts</CardDescription>
            </CardHeader>
            <CardContent className="space-y-2">
              <Button className="w-full justify-start" asChild>
                <Link href="/feeds">
                  <Database className="mr-2 h-4 w-4" />
                  Add New Feed
                </Link>
              </Button>
              <Button className="w-full justify-start" variant="outline" asChild>
                <Link href="/api-keys">
                  <Key className="mr-2 h-4 w-4" />
                  Generate API Key
                </Link>
              </Button>
              <Button className="w-full justify-start" variant="outline" asChild>
                <Link href="/organizations">
                  <Building2 className="mr-2 h-4 w-4" />
                  Create Organization
                </Link>
              </Button>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Recent Activity</CardTitle>
              <CardDescription>Latest updates and changes</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div className="flex items-center">
                  <div className="w-2 h-2 bg-green-500 rounded-full mr-3" />
                  <div className="flex-1">
                    <p className="text-sm font-medium">New feed added</p>
                    <p className="text-xs text-muted-foreground">2 hours ago</p>
                  </div>
                </div>
                <div className="flex items-center">
                  <div className="w-2 h-2 bg-blue-500 rounded-full mr-3" />
                  <div className="flex-1">
                    <p className="text-sm font-medium">API key generated</p>
                    <p className="text-xs text-muted-foreground">5 hours ago</p>
                  </div>
                </div>
                <div className="flex items-center">
                  <div className="w-2 h-2 bg-yellow-500 rounded-full mr-3" />
                  <div className="flex-1">
                    <p className="text-sm font-medium">Organization updated</p>
                    <p className="text-xs text-muted-foreground">1 day ago</p>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </DashboardLayout>
  );
}

