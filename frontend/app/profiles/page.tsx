"use client"

import { useState, useEffect } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Badge } from "@/components/ui/badge"
import { Plus, Power, Pencil, RefreshCw } from "lucide-react"
import { AddProfileModal } from "@/components/add-profile-modal"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { api } from "@/lib/api"
import { useToast } from "@/hooks/use-toast"

const STORAGE_STATE_SAMPLE = `{
  "cookies": [
    {
      "name": "li_at",
      "value": "your-cookie-value",
      "domain": ".linkedin.com",
      "path": "/",
      "expires": -1,
      "httpOnly": true,
      "secure": true,
      "sameSite": "None"
    }
  ],
  "origins": []
}`

export default function ProfilesPage() {
  const [profiles, setProfiles] = useState<any[]>([])
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [isLoading, setIsLoading] = useState(true)
  const [renameDialogOpen, setRenameDialogOpen] = useState(false)
  const [senderToRename, setSenderToRename] = useState<any>(null)
  const [newSenderName, setNewSenderName] = useState("")
  const [isRenaming, setIsRenaming] = useState(false)
  const [updateDialogOpen, setUpdateDialogOpen] = useState(false)
  const [senderToUpdate, setSenderToUpdate] = useState<any>(null)
  const [updateName, setUpdateName] = useState("")
  const [updateStorageState, setUpdateStorageState] = useState("")
  const [isUpdating, setIsUpdating] = useState(false)
  const { toast } = useToast()

  // Fetch senders on component mount
  useEffect(() => {
    fetchSenders()
  }, [])

  const fetchSenders = async () => {
    setIsLoading(true)
    try {
      const sendersData = await api.getSenders()
      setProfiles(sendersData)
    } catch (error) {
      toast({
        title: "Error",
        description: error instanceof Error ? error.message : "Failed to load sender profiles",
        variant: "destructive",
      })
    } finally {
      setIsLoading(false)
    }
  }

  const handleAddProfile = async (data: { name: string; storage_state?: string }) => {
    try {
      await api.createSender(data)
      toast({
        title: "Success",
        description: "Sender profile added successfully",
      })
      setIsModalOpen(false)
      await fetchSenders()
    } catch (error) {
      toast({
        title: "Error",
        description: error instanceof Error ? error.message : "Failed to add sender profile",
        variant: "destructive",
      })
    }
  }

  const handleUpdateClick = async (profile: any) => {
    // Fetch fresh data for this specific sender to ensure we have the latest storage_state
    try {
      const allSenders = await api.getSenders()
      const freshSender = allSenders.find((s: any) => s.id === profile.id)
      const senderToUse = freshSender || profile
      
      setSenderToUpdate(senderToUse)
      setUpdateName(senderToUse.name || "")
      
      // Handle storage_state - format it nicely for display
      let formattedStorageState = ""
      const storageState = senderToUse.storage_state
      
      // Check if storage_state exists and is not null/undefined/empty
      if (storageState !== null && storageState !== undefined && storageState !== "") {
        try {
          // If it's already a string, try to parse and reformat for pretty display
          if (typeof storageState === 'string' && storageState.trim().length > 0) {
            // Parse the JSON string and reformat it with proper indentation
            const parsed = JSON.parse(storageState)
            formattedStorageState = JSON.stringify(parsed, null, 2)
          } else if (typeof storageState === 'object' && storageState !== null) {
            // If it's an object, stringify with formatting
            formattedStorageState = JSON.stringify(storageState, null, 2)
          } else {
            // If it's something else, convert to string
            formattedStorageState = String(storageState)
          }
        } catch (e) {
          // If parsing fails, use as-is but still try to format if it looks like JSON
          console.error("Error parsing storage_state:", e)
          formattedStorageState = String(storageState)
        }
      }
      
      setUpdateStorageState(formattedStorageState)
      setUpdateDialogOpen(true)
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to load sender data. Using cached data.",
        variant: "destructive",
      })
      // Fallback to using the profile data we have
      setSenderToUpdate(profile)
      setUpdateName(profile.name || "")
      setUpdateStorageState(profile.storage_state ? (typeof profile.storage_state === 'string' ? profile.storage_state : JSON.stringify(profile.storage_state, null, 2)) : "")
      setUpdateDialogOpen(true)
    }
  }

  const handleUpdate = async () => {
    if (!senderToUpdate || !updateName.trim()) {
      toast({
        title: "Error",
        description: "Please enter a sender name",
        variant: "destructive",
      })
      return
    }

    setIsUpdating(true)
    try {
      const updateData: { name: string; storage_state?: string } = {
        name: updateName.trim(),
      }
      
      // Only include storage_state if it's not empty
      if (updateStorageState.trim()) {
        updateData.storage_state = updateStorageState.trim()
      }
      
      await api.updateSender(senderToUpdate.id, updateData)
      toast({
        title: "Success",
        description: "Sender profile updated successfully",
      })
      setUpdateDialogOpen(false)
      setSenderToUpdate(null)
      setUpdateName("")
      setUpdateStorageState("")
      await fetchSenders()
    } catch (error) {
      toast({
        title: "Error",
        description: error instanceof Error ? error.message : "Failed to update sender profile",
        variant: "destructive",
      })
    } finally {
      setIsUpdating(false)
    }
  }

  const handleToggleSender = async (senderId: string, currentEnabled: boolean) => {
    try {
      const result = await api.toggleSender(senderId)
      // Refresh the list to show updated status
      await fetchSenders()
      toast({
        title: "Success",
        description: `Sender ${result.enabled ? "enabled" : "disabled"} successfully`,
      })
    } catch (error) {
      toast({
        title: "Error",
        description: error instanceof Error ? error.message : "Failed to toggle sender status",
        variant: "destructive",
      })
    }
  }

  const handleRenameClick = (profile: any) => {
    setSenderToRename(profile)
    setNewSenderName(profile.name || "")
    setRenameDialogOpen(true)
  }

  const handleRename = async () => {
    if (!senderToRename || !newSenderName.trim()) {
      toast({
        title: "Error",
        description: "Please enter a sender name",
        variant: "destructive",
      })
      return
    }

    setIsRenaming(true)
    try {
      await api.updateSender(senderToRename.id, { name: newSenderName.trim() })
      toast({
        title: "Success",
        description: "Sender renamed successfully",
      })
      setRenameDialogOpen(false)
      setSenderToRename(null)
      setNewSenderName("")
      await fetchSenders()
    } catch (error) {
      toast({
        title: "Error",
        description: error instanceof Error ? error.message : "Failed to rename sender",
        variant: "destructive",
      })
    } finally {
      setIsRenaming(false)
    }
  }

  const enabledCount = profiles.filter((p) => p.enabled === true).length
  const disabledCount = profiles.filter((p) => p.enabled === false).length

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Sender Profiles</h1>
          <p className="text-muted-foreground mt-2">Manage LinkedIn sender accounts used for sending messages</p>
        </div>
        <Button onClick={() => setIsModalOpen(true)} className="shadow-sm">
          <Plus className="mr-2 h-4 w-4" />
          Add Profile
        </Button>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <Card className="shadow-sm">
          <CardHeader className="pb-3">
            <CardDescription>Enabled Profiles</CardDescription>
            <CardTitle className="text-3xl">{enabledCount}</CardTitle>
          </CardHeader>
        </Card>
        <Card className="shadow-sm">
          <CardHeader className="pb-3">
            <CardDescription>Disabled Profiles</CardDescription>
            <CardTitle className="text-3xl">{disabledCount}</CardTitle>
          </CardHeader>
        </Card>
      </div>

      <Card className="shadow-sm">
        <CardHeader>
          <CardTitle>All Sender Profiles</CardTitle>
          <CardDescription>LinkedIn sender accounts configured for outreach campaigns</CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Sender Name</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Last Updated</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {isLoading ? (
                <TableRow>
                  <TableCell colSpan={4} className="text-center text-muted-foreground">
                    Loading sender profiles...
                  </TableCell>
                </TableRow>
              ) : profiles.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={4} className="text-center text-muted-foreground">
                    No sender profiles found
                  </TableCell>
                </TableRow>
              ) : (
                profiles.map((profile) => (
                  <TableRow key={profile.id}>
                    <TableCell className="font-medium">
                      <div className="flex items-center gap-2">
                        <span>{profile.name || "Unnamed"}</span>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleRenameClick(profile)}
                          className="h-6 w-6 p-0"
                        >
                          <Pencil className="h-3 w-3" />
                        </Button>
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge variant={profile.enabled ? "default" : "secondary"}>
                        {profile.enabled ? "Enabled" : "Disabled"}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {profile.updated_at
                        ? new Date(profile.updated_at).toLocaleDateString("en-US", {
                            year: "numeric",
                            month: "short",
                            day: "numeric",
                            hour: "2-digit",
                            minute: "2-digit",
                          })
                        : "N/A"}
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex items-center justify-end gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleUpdateClick(profile)}
                          className="gap-2"
                        >
                          <RefreshCw className="h-4 w-4" />
                          Update
                        </Button>
                        <Button
                          variant={profile.enabled ? "destructive" : "default"}
                          size="sm"
                          onClick={() => handleToggleSender(profile.id, profile.enabled)}
                          className="gap-2"
                        >
                          <Power className="h-4 w-4" />
                          {profile.enabled ? "Disable" : "Enable"}
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <AddProfileModal open={isModalOpen} onOpenChange={setIsModalOpen} onSubmit={handleAddProfile} />

      <Dialog open={renameDialogOpen} onOpenChange={setRenameDialogOpen}>
        <DialogContent className="sm:max-w-[425px]">
          <DialogHeader>
            <DialogTitle>Rename Sender</DialogTitle>
            <DialogDescription>
              Enter a new name for this sender profile.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="name">Sender Name</Label>
              <Input
                id="name"
                value={newSenderName}
                onChange={(e) => setNewSenderName(e.target.value)}
                placeholder="Enter sender name"
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault()
                    handleRename()
                  }
                }}
              />
            </div>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setRenameDialogOpen(false)}>
              Cancel
            </Button>
            <Button type="button" onClick={handleRename} disabled={isRenaming || !newSenderName.trim()}>
              {isRenaming ? "Renaming..." : "Rename"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={updateDialogOpen} onOpenChange={setUpdateDialogOpen}>
        <DialogContent className="sm:max-w-[600px] max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Update Sender Profile</DialogTitle>
            <DialogDescription>
              Update the name and storage state (cookies) for this sender profile.
              {senderToUpdate && (
                <span className="block mt-1 text-xs">
                  Current Sender ID: <code className="text-xs bg-muted px-1 rounded">{senderToUpdate.id}</code>
                </span>
              )}
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="update-name">Sender Name</Label>
              <Input
                id="update-name"
                value={updateName}
                onChange={(e) => setUpdateName(e.target.value)}
                placeholder="Enter sender name"
                required
              />
              {senderToUpdate && senderToUpdate.name && (
                <p className="text-xs text-muted-foreground">
                  Current name: <span className="font-medium">{senderToUpdate.name}</span>
                </p>
              )}
            </div>
            <div className="grid gap-2">
              <Label htmlFor="update-storage-state">Storage State (Cookies JSON)</Label>
              <Textarea
                id="update-storage-state"
                value={updateStorageState}
                onChange={(e) => setUpdateStorageState(e.target.value)}
                placeholder={STORAGE_STATE_SAMPLE}
                rows={12}
                className="font-mono text-sm"
              />
              <p className="text-xs text-muted-foreground">
                {updateStorageState.trim() 
                  ? "Storage state JSON from Playwright. Edit above to update. Leave empty to remove current storage state."
                  : "No storage state currently set. Paste JSON above to add one, or leave empty to keep it removed."}
              </p>
            </div>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setUpdateDialogOpen(false)}>
              Cancel
            </Button>
            <Button type="button" onClick={handleUpdate} disabled={isUpdating || !updateName.trim()}>
              {isUpdating ? "Updating..." : "Update"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
