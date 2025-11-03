"use client"

import { useState, useEffect, use } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Badge } from "@/components/ui/badge"
import { ArrowLeft } from "lucide-react"
import Link from "next/link"
import { api } from "@/lib/api"
import { useToast } from "@/hooks/use-toast"

export default function ListDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params)
  const [list, setList] = useState<any>(null)
  const [profiles, setProfiles] = useState<any[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [isLoadingProfiles, setIsLoadingProfiles] = useState(true)
  const { toast } = useToast()

  useEffect(() => {
    const fetchListData = async () => {
      try {
        setIsLoading(true)
        setIsLoadingProfiles(true)
        // Fetch list details and prospects in parallel
        const [listData, prospectsData] = await Promise.all([
          api.getList(id),
          api.getListProspects(id),
        ])
        setList(listData)
        setProfiles(prospectsData)
      } catch (error) {
        toast({
          title: "Error",
          description: error instanceof Error ? error.message : "Failed to load list data",
          variant: "destructive",
        })
      } finally {
        setIsLoading(false)
        setIsLoadingProfiles(false)
      }
    }

    if (id) {
      fetchListData()
    }
  }, [id, toast])

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-4">
          <Link href="/lists">
            <Button variant="outline" size="icon" className="shadow-sm bg-transparent">
              <ArrowLeft className="h-4 w-4" />
            </Button>
          </Link>
          <div>
            <div className="h-8 w-48 bg-muted animate-pulse rounded" />
            <div className="h-4 w-64 bg-muted animate-pulse rounded mt-2" />
          </div>
        </div>
        <Card>
          <CardContent className="pt-6">
            <div className="text-center text-muted-foreground">Loading list data...</div>
          </CardContent>
        </Card>
      </div>
    )
  }

  if (!list) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-4">
          <Link href="/lists">
            <Button variant="outline" size="icon" className="shadow-sm bg-transparent">
              <ArrowLeft className="h-4 w-4" />
            </Button>
          </Link>
        </div>
        <Card>
          <CardContent className="pt-6">
            <div className="text-center text-muted-foreground">List not found</div>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Link href="/lists">
          <Button variant="outline" size="icon" className="shadow-sm bg-transparent">
            <ArrowLeft className="h-4 w-4" />
          </Button>
        </Link>
        <div>
          <h1 className="text-3xl font-bold tracking-tight">{list.name}</h1>
          <p className="text-muted-foreground mt-2">
            {profiles.length} profiles • Created on{" "}
            {list.created_at
              ? new Date(list.created_at).toLocaleDateString("en-US", {
                  year: "numeric",
                  month: "long",
                  day: "numeric",
                })
              : "N/A"}
          </p>
        </div>
      </div>

      <Card className="shadow-sm">
        <CardHeader>
          <CardTitle>Profiles</CardTitle>
          <CardDescription>All LinkedIn profiles in this list</CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Profile URL</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Invite Note</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {isLoadingProfiles ? (
                <TableRow>
                  <TableCell colSpan={4} className="text-center text-muted-foreground">
                    Loading profiles...
                  </TableCell>
                </TableRow>
              ) : profiles.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={4} className="text-center text-muted-foreground">
                    No profiles found in this list
                  </TableCell>
                </TableRow>
              ) : (
                profiles.map((profile) => (
                  <TableRow key={profile.profile_url || profile.id} className="cursor-pointer hover:bg-muted/50">
                    <TableCell className="font-medium">
                      {profile.full_name || profile.first_name || "N/A"}
                    </TableCell>
                    <TableCell>
                      <a 
                        href={profile.profile_url} 
                        target="_blank" 
                        rel="noopener noreferrer"
                        className="text-primary hover:underline text-sm"
                      >
                        {profile.profile_url}
                      </a>
                    </TableCell>
                    <TableCell>
                      <Badge 
                        variant={
                          profile.status === "connected" 
                            ? "default" 
                            : profile.status === "invited" 
                            ? "secondary"
                            : "outline"
                        }
                      >
                        {profile.status || "new"}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-muted-foreground text-sm">
                      {profile.note_text || "—"}
                    </TableCell>
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
