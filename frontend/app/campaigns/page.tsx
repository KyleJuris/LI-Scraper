"use client"

import { useState } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Badge } from "@/components/ui/badge"
import { Plus } from "lucide-react"
import { CreateCampaignModal } from "@/components/create-campaign-modal"
import Link from "next/link"
import { api } from "@/lib/api"
import { useToast } from "@/hooks/use-toast"

export default function CampaignsPage() {
  const [campaigns, setCampaigns] = useState<any[]>([])
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const { toast } = useToast()

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "completed":
        return <Badge className="bg-green-500/10 text-green-500 hover:bg-green-500/20">Completed</Badge>
      case "running":
        return <Badge className="bg-blue-500/10 text-blue-500 hover:bg-blue-500/20">Running</Badge>
      case "draft":
        return <Badge variant="secondary">Draft</Badge>
      default:
        return <Badge variant="outline">{status}</Badge>
    }
  }

  const handleCreateCampaign = async (campaignData: {
    name: string
    listId: string
    profileId: string
    message: string
  }) => {
    setIsLoading(true)
    try {
      const result = await api.sendCampaign({
        limit: 20,
        default_dm: campaignData.message,
      })
      const newCampaign = {
        id: campaigns.length + 1,
        name: campaignData.name,
        list_name: "Selected List",
        message: campaignData.message,
        status: "running",
      }
      setCampaigns([...campaigns, newCampaign])
      setIsModalOpen(false)
      toast({
        title: "Success",
        description: `Campaign started: ${result.sent} messages sent, ${result.errors} errors`,
      })
    } catch (error) {
      toast({
        title: "Error",
        description: error instanceof Error ? error.message : "Failed to start campaign",
        variant: "destructive",
      })
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Campaigns</h1>
          <p className="text-muted-foreground mt-2">Create and manage your LinkedIn outreach campaigns</p>
        </div>
        <Button onClick={() => setIsModalOpen(true)} className="gap-2 shadow-sm">
          <Plus className="h-4 w-4" />
          Create New Campaign
        </Button>
      </div>

      <Card className="shadow-sm">
        <CardHeader>
          <CardTitle>All Campaigns</CardTitle>
          <CardDescription>View and manage all your outreach campaigns</CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Campaign Name</TableHead>
                <TableHead>Associated List</TableHead>
                <TableHead>Message Preview</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {campaigns.map((campaign) => (
                <TableRow key={campaign.id} className="cursor-pointer hover:bg-muted/50">
                  <TableCell className="font-medium">
                    <Link href={`/campaigns/${campaign.id}`} className="text-primary hover:underline">
                      {campaign.name}
                    </Link>
                  </TableCell>
                  <TableCell>{campaign.list_name}</TableCell>
                  <TableCell className="max-w-xs truncate text-muted-foreground">{campaign.message}</TableCell>
                  <TableCell>{getStatusBadge(campaign.status)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <CreateCampaignModal open={isModalOpen} onOpenChange={setIsModalOpen} onSubmit={handleCreateCampaign} disabled={isLoading} />
    </div>
  )
}
