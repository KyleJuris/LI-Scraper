"use client"

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Badge } from "@/components/ui/badge"
import { ArrowLeft } from "lucide-react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { useState, useEffect } from "react"

export default function ProfilePage({ params }: { params: { username: string } }) {
  const router = useRouter()
  const [profileData, setProfileData] = useState<any>(null)
  const [messages, setMessages] = useState<any[]>([])

  useEffect(() => {
    // TODO: Fetch prospect data from API based on profile_url
    // For now, construct profile_url from username
    const profileUrl = `https://www.linkedin.com/in/${params.username}/`
    // Load profile data and messages from API
  }, [params.username])

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

  if (!profileData) {
    return (
      <div className="space-y-6">
        <Button variant="outline" onClick={() => router.back()} className="gap-2 shadow-sm">
          <ArrowLeft className="h-4 w-4" />
          Go Back
        </Button>
        <div>Profile not found</div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Button variant="outline" size="icon" onClick={() => router.back()} className="shadow-sm bg-transparent">
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <div>
          <h1 className="text-3xl font-bold tracking-tight">{profileData.profile_url || params.username}</h1>
          <p className="text-muted-foreground mt-2">
            {profileData.first_name ? `${profileData.first_name}'s LinkedIn Profile` : "LinkedIn Profile"}
          </p>
        </div>
      </div>

      <Card className="shadow-sm">
        <CardHeader>
          <CardTitle>Profile Details</CardTitle>
          <CardDescription>Information about this LinkedIn prospect</CardDescription>
        </CardHeader>
        <CardContent className="space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-sm text-muted-foreground">Profile URL</span>
            <a href={profileData.profile_url} target="_blank" rel="noopener noreferrer" className="font-medium text-primary hover:underline">
              {profileData.profile_url}
            </a>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-sm text-muted-foreground">First Name</span>
            <span className="font-medium">{profileData.first_name || "N/A"}</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-sm text-muted-foreground">Status</span>
            <Badge variant={profileData.status === "connected" ? "default" : "secondary"}>
              {profileData.status || "pending"}
            </Badge>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-sm text-muted-foreground">Total Messages Sent</span>
            <span className="font-medium">{messages.length}</span>
          </div>
        </CardContent>
      </Card>

      <Card className="shadow-sm">
        <CardHeader>
          <CardTitle>All Messages Sent</CardTitle>
          <CardDescription>Complete history of all messages sent to this prospect across all campaigns</CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Campaign</TableHead>
                <TableHead>Message</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Sent At</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {messages.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={4} className="text-center text-muted-foreground">
                    No messages sent to this prospect yet
                  </TableCell>
                </TableRow>
              ) : (
                messages.map((message) => (
                  <TableRow key={message.id}>
                    <TableCell className="font-medium">
                      <Link href={`/campaigns/${message.campaign_id}`} className="text-primary hover:underline">
                        {message.campaign_name || "Unknown Campaign"}
                      </Link>
                    </TableCell>
                    <TableCell className="max-w-md truncate text-muted-foreground">{message.dm_text || message.message || "N/A"}</TableCell>
                    <TableCell>{getStatusBadge(message.status || "pending")}</TableCell>
                    <TableCell className="text-muted-foreground text-sm">{message.sent_at || "Not sent yet"}</TableCell>
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
