"use client"

import { useState } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Badge } from "@/components/ui/badge"
import { ArrowLeft } from "lucide-react"
import Link from "next/link"

export default function CampaignDetailPage({ params }: { params: { id: string } }) {
  const [campaign, setCampaign] = useState<any>(null)
  const [users, setUsers] = useState<any[]>([])

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "sent":
        return <Badge className="bg-green-500/10 text-green-500 hover:bg-green-500/20">Sent</Badge>
      case "pending":
        return <Badge variant="secondary">Pending</Badge>
      case "failed":
        return <Badge variant="destructive">Failed</Badge>
      default:
        return <Badge variant="outline">{status}</Badge>
    }
  }

  const getCampaignStatusBadge = (status: string) => {
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

  if (!campaign) {
    return <div>Campaign not found</div>
  }

  // Calculate stats from users

  const sentCount = users.filter((u) => u.dm_status === "sent").length
  const pendingCount = users.filter((u) => u.dm_status === "pending").length
  const failedCount = users.filter((u) => u.dm_status === "failed").length

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Link href="/campaigns">
          <Button variant="outline" size="icon" className="shadow-sm bg-transparent">
            <ArrowLeft className="h-4 w-4" />
          </Button>
        </Link>
        <div className="flex-1">
          <div className="flex items-center gap-3">
            <h1 className="text-3xl font-bold tracking-tight">{campaign.name}</h1>
            {getCampaignStatusBadge(campaign.status)}
          </div>
          <p className="text-muted-foreground mt-2">
            Sent from <span className="font-medium">{campaign.sender_profile}</span> • Associated with{" "}
            <span className="font-medium">{campaign.list_name}</span> • Created on{" "}
            {new Date(campaign.created_at).toLocaleDateString("en-US", {
              year: "numeric",
              month: "long",
              day: "numeric",
            })}
          </p>
        </div>
      </div>

      <Card className="shadow-sm">
        <CardHeader>
          <CardTitle>Campaign Message</CardTitle>
          <CardDescription>The DM template sent to all users in this campaign</CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-sm leading-relaxed">{campaign.message}</p>
        </CardContent>
      </Card>

      <div className="grid gap-4 md:grid-cols-3">
        <Card className="shadow-sm">
          <CardHeader className="pb-3">
            <CardDescription>Sent</CardDescription>
            <CardTitle className="text-3xl">{sentCount}</CardTitle>
          </CardHeader>
        </Card>
        <Card className="shadow-sm">
          <CardHeader className="pb-3">
            <CardDescription>Pending</CardDescription>
            <CardTitle className="text-3xl">{pendingCount}</CardTitle>
          </CardHeader>
        </Card>
        <Card className="shadow-sm">
          <CardHeader className="pb-3">
            <CardDescription>Failed</CardDescription>
            <CardTitle className="text-3xl">{failedCount}</CardTitle>
          </CardHeader>
        </Card>
      </div>

      <Card className="shadow-sm">
        <CardHeader>
          <CardTitle>Campaign Prospects</CardTitle>
          <CardDescription>All prospects targeted in this campaign with their DM status</CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Profile URL</TableHead>
                <TableHead>First Name</TableHead>
                <TableHead>DM Status</TableHead>
                <TableHead>Sent At</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {users.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={4} className="text-center text-muted-foreground">
                    No prospects found for this campaign
                  </TableCell>
                </TableRow>
              ) : (
                users.map((user) => (
                  <TableRow key={user.id}>
                    <TableCell className="font-medium">
                      <Link href={user.profile_url} target="_blank" className="text-primary hover:underline">
                        {user.profile_url}
                      </Link>
                    </TableCell>
                    <TableCell>{user.first_name || "N/A"}</TableCell>
                    <TableCell>{getStatusBadge(user.dm_status || "pending")}</TableCell>
                    <TableCell className="text-muted-foreground text-sm">{user.sent_at || "Not sent yet"}</TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  )
}
