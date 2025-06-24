import React, { useState, useEffect } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from './ui/card';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Textarea } from './ui/textarea';
import { Badge } from './ui/badge';
import { Alert, AlertDescription } from './ui/alert';
import { Tabs, TabsContent, TabsList, TabsTrigger } from './ui/tabs';
import { 
  Play, 
  Pause, 
  Plus, 
  Settings, 
  BarChart3, 
  AlertTriangle, 
  CheckCircle, 
  XCircle,
  Eye,
  Target
} from 'lucide-react';

const DiscordPromotion = () => {
  const [campaigns, setCampaigns] = useState([]);
  const [accounts, setAccounts] = useState([]);
  const [selectedCampaign, setSelectedCampaign] = useState(null);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [loading, setLoading] = useState(false);
  const [alerts, setAlerts] = useState([]);

  // Form state for creating new campaign
  const [newCampaign, setNewCampaign] = useState({
    name: '',
    description: '',
    discord_url: '',
    short_url: '',
    post_title: 'Norsk NSFW Gruppe - Deilig innhold deles daglig - Grovt & digg.',
    use_template: true
  });

  useEffect(() => {
    loadCampaigns();
    loadAccounts();
  }, []);

  const loadCampaigns = async () => {
    try {
      const response = await fetch('/api/discord-promotion/campaigns');
      const data = await response.json();
      setCampaigns(data);
    } catch (error) {
      console.error('Error loading campaigns:', error);
    }
  };

  const loadAccounts = async () => {
    try {
      const response = await fetch('/api/reddit/accounts');
      const data = await response.json();
      setAccounts(data.accounts || []);
    } catch (error) {
      console.error('Error loading accounts:', error);
    }
  };

  const createCampaign = async () => {
    setLoading(true);
    try {
      const endpoint = newCampaign.use_template 
        ? '/api/discord-promotion/campaigns/quick-setup'
        : '/api/discord-promotion/campaigns';
      
      const payload = newCampaign.use_template
        ? {
            name: newCampaign.name,
            discord_url: newCampaign.discord_url,
            short_url: newCampaign.short_url,
            custom_title: newCampaign.post_title !== 'Norsk NSFW Gruppe - Deilig innhold deles daglig - Grovt & digg.' 
              ? newCampaign.post_title : null
          }
        : newCampaign;

      const response = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (response.ok) {
        await loadCampaigns();
        setShowCreateForm(false);
        setNewCampaign({
          name: '',
          description: '',
          discord_url: '',
          short_url: '',
          post_title: 'Norsk NSFW Gruppe - Deilig innhold deles daglig - Grovt & digg.',
          use_template: true
        });
      }
    } catch (error) {
      console.error('Error creating campaign:', error);
    }
    setLoading(false);
  };

  const startCampaign = async (campaignId) => {
    try {
      const validAccounts = accounts.filter(acc => acc.is_valid).map(acc => acc.id);
      
      const response = await fetch(`/api/discord-promotion/campaigns/${campaignId}/schedule`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ account_ids: validAccounts })
      });

      if (response.ok) {
        await loadCampaigns();
      }
    } catch (error) {
      console.error('Error starting campaign:', error);
    }
  };

  const stopCampaign = async (campaignId) => {
    try {
      const response = await fetch(`/api/discord-promotion/campaigns/${campaignId}/schedule/stop`, {
        method: 'POST'
      });

      if (response.ok) {
        await loadCampaigns();
      }
    } catch (error) {
      console.error('Error stopping campaign:', error);
    }
  };

  const testPost = async (campaignId) => {
    try {
      const validAccounts = accounts.filter(acc => acc.is_valid);
      if (validAccounts.length === 0) {
        alert('No valid accounts available for testing');
        return;
      }

      const response = await fetch(`/api/discord-promotion/campaigns/${campaignId}/test-post`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          campaign_id: campaignId,
          account_id: validAccounts[0].id 
        })
      });

      const result = await response.json();
      alert(result.message || 'Test post initiated');
    } catch (error) {
      console.error('Error testing post:', error);
    }
  };

  const loadCampaignAlerts = async (campaignId) => {
    try {
      const response = await fetch(`/api/discord-promotion/campaigns/${campaignId}/alerts`);
      const data = await response.json();
      setAlerts(data.alerts || []);
    } catch (error) {
      console.error('Error loading alerts:', error);
    }
  };

  const CampaignCard = ({ campaign }) => (
    <Card className="mb-4">
      <CardHeader>
        <div className="flex justify-between items-start">
          <div>
            <CardTitle className="flex items-center gap-2">
              {campaign.name}
              <Badge variant={campaign.is_active ? "default" : "secondary"}>
                {campaign.is_active ? "Active" : "Inactive"}
              </Badge>
            </CardTitle>
            <p className="text-sm text-gray-600 mt-1">{campaign.description}</p>
          </div>
          <div className="flex gap-2">
            {campaign.is_active ? (
              <Button 
                size="sm" 
                variant="outline" 
                onClick={() => stopCampaign(campaign.id)}
              >
                <Pause className="w-4 h-4 mr-1" />
                Stop
              </Button>
            ) : (
              <Button 
                size="sm" 
                onClick={() => startCampaign(campaign.id)}
              >
                <Play className="w-4 h-4 mr-1" />
                Start
              </Button>
            )}
            <Button 
              size="sm" 
              variant="outline"
              onClick={() => testPost(campaign.id)}
            >
              <Eye className="w-4 h-4 mr-1" />
              Test
            </Button>
            <Button 
              size="sm" 
              variant="outline"
              onClick={() => {
                setSelectedCampaign(campaign);
                loadCampaignAlerts(campaign.id);
              }}
            >
              <BarChart3 className="w-4 h-4 mr-1" />
              Details
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
          <div>
            <span className="font-medium">Discord URL:</span>
            <p className="text-blue-600 truncate">{campaign.discord_url}</p>
          </div>
          <div>
            <span className="font-medium">Total Posts:</span>
            <p>{campaign.total_posts}</p>
          </div>
          <div>
            <span className="font-medium">Success Rate:</span>
            <p className={campaign.success_rate > 70 ? "text-green-600" : campaign.success_rate > 40 ? "text-yellow-600" : "text-red-600"}>
              {campaign.success_rate.toFixed(1)}%
            </p>
          </div>
          <div>
            <span className="font-medium">Subreddits:</span>
            <p>{campaign.preferred_subreddits?.length || 0} preferred</p>
          </div>
        </div>
        
        <div className="mt-3">
          <span className="font-medium text-sm">Post Title:</span>
          <p className="text-sm text-gray-700 italic">"{campaign.post_title}"</p>
        </div>
      </CardContent>
    </Card>
  );

  const CreateCampaignForm = () => (
    <Card>
      <CardHeader>
        <CardTitle>Create Discord Promotion Campaign</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div>
          <label className="block text-sm font-medium mb-1">Campaign Name</label>
          <Input
            value={newCampaign.name}
            onChange={(e) => setNewCampaign({...newCampaign, name: e.target.value})}
            placeholder="My Discord Server Promotion"
          />
        </div>

        <div>
          <label className="block text-sm font-medium mb-1">Discord Server URL</label>
          <Input
            value={newCampaign.discord_url}
            onChange={(e) => setNewCampaign({...newCampaign, discord_url: e.target.value})}
            placeholder="http://discord.gg/YourServer"
          />
        </div>

        <div>
          <label className="block text-sm font-medium mb-1">Short URL (Optional)</label>
          <Input
            value={newCampaign.short_url}
            onChange={(e) => setNewCampaign({...newCampaign, short_url: e.target.value})}
            placeholder="https://3ly.link/shortened"
          />
        </div>

        <div>
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={newCampaign.use_template}
              onChange={(e) => setNewCampaign({...newCampaign, use_template: e.target.checked})}
            />
            <span className="text-sm">Use Norwegian NSFW template (recommended)</span>
          </label>
        </div>

        <div>
          <label className="block text-sm font-medium mb-1">Post Title</label>
          <Input
            value={newCampaign.post_title}
            onChange={(e) => setNewCampaign({...newCampaign, post_title: e.target.value})}
            placeholder="Post title for Reddit submissions"
          />
        </div>

        {!newCampaign.use_template && (
          <div>
            <label className="block text-sm font-medium mb-1">Description</label>
            <Textarea
              value={newCampaign.description}
              onChange={(e) => setNewCampaign({...newCampaign, description: e.target.value})}
              placeholder="Campaign description"
            />
          </div>
        )}

        <div className="flex gap-2">
          <Button onClick={createCampaign} disabled={loading}>
            {loading ? 'Creating...' : 'Create Campaign'}
          </Button>
          <Button variant="outline" onClick={() => setShowCreateForm(false)}>
            Cancel
          </Button>
        </div>
      </CardContent>
    </Card>
  );

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-3xl font-bold">Discord Server Promotion</h1>
        <Button onClick={() => setShowCreateForm(true)}>
          <Plus className="w-4 h-4 mr-2" />
          New Campaign
        </Button>
      </div>

      {/* Account Status Alert */}
      <Alert className="mb-6">
        <AlertTriangle className="h-4 w-4" />
        <AlertDescription>
          Connected Accounts: {accounts.filter(acc => acc.is_valid).length} valid, {accounts.filter(acc => !acc.is_valid).length} invalid.
          {accounts.filter(acc => acc.is_valid).length === 0 && (
            <span className="text-red-600 ml-2">
              No valid accounts available. Please connect Reddit accounts first.
            </span>
          )}
        </AlertDescription>
      </Alert>

      {showCreateForm ? (
        <CreateCampaignForm />
      ) : (
        <Tabs defaultValue="campaigns" className="w-full">
          <TabsList>
            <TabsTrigger value="campaigns">Campaigns</TabsTrigger>
            <TabsTrigger value="analytics">Analytics</TabsTrigger>
            <TabsTrigger value="settings">Settings</TabsTrigger>
          </TabsList>

          <TabsContent value="campaigns" className="mt-6">
            {campaigns.length === 0 ? (
              <Card>
                <CardContent className="text-center py-8">
                  <Target className="w-12 h-12 mx-auto text-gray-400 mb-4" />
                  <h3 className="text-lg font-medium mb-2">No campaigns yet</h3>
                  <p className="text-gray-600 mb-4">Create your first Discord promotion campaign to get started.</p>
                  <Button onClick={() => setShowCreateForm(true)}>
                    <Plus className="w-4 h-4 mr-2" />
                    Create Campaign
                  </Button>
                </CardContent>
              </Card>
            ) : (
              campaigns.map(campaign => (
                <CampaignCard key={campaign.id} campaign={campaign} />
              ))
            )}
          </TabsContent>

          <TabsContent value="analytics" className="mt-6">
            <Card>
              <CardHeader>
                <CardTitle>Campaign Analytics</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-gray-600">Select a campaign to view detailed analytics and performance metrics.</p>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="settings" className="mt-6">
            <Card>
              <CardHeader>
                <CardTitle>Promotion Settings</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-gray-600">Global settings for Discord promotion campaigns will be available here.</p>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      )}

      {/* Campaign Details Modal/Sidebar would go here */}
      {selectedCampaign && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <Card className="w-full max-w-4xl max-h-[90vh] overflow-y-auto">
            <CardHeader>
              <div className="flex justify-between items-start">
                <CardTitle>{selectedCampaign.name} - Details</CardTitle>
                <Button variant="outline" onClick={() => setSelectedCampaign(null)}>
                  ×
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              {alerts.length > 0 && (
                <div className="mb-4">
                  <h4 className="font-medium mb-2">Alerts & Warnings</h4>
                  {alerts.map((alert, index) => (
                    <Alert key={index} className={`mb-2 ${alert.severity === 'critical' ? 'border-red-500' : 'border-yellow-500'}`}>
                      <AlertTriangle className="h-4 w-4" />
                      <AlertDescription>
                        <strong>{alert.type}:</strong> {alert.message}
                        <br />
                        <em>Recommendation: {alert.recommendation}</em>
                      </AlertDescription>
                    </Alert>
                  ))}
                </div>
              )}
              
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <h4 className="font-medium mb-2">Campaign Info</h4>
                  <p><strong>Discord URL:</strong> {selectedCampaign.discord_url}</p>
                  <p><strong>Post Title:</strong> {selectedCampaign.post_title}</p>
                  <p><strong>Total Posts:</strong> {selectedCampaign.total_posts}</p>
                  <p><strong>Success Rate:</strong> {selectedCampaign.success_rate.toFixed(1)}%</p>
                </div>
                <div>
                  <h4 className="font-medium mb-2">Subreddits</h4>
                  <p><strong>Preferred:</strong> {selectedCampaign.preferred_subreddits?.join(', ')}</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
};

export default DiscordPromotion;
