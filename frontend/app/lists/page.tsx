"use client"

import { useState, useEffect } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Checkbox } from "@/components/ui/checkbox"
import { Textarea } from "@/components/ui/textarea"
import Link from "next/link"
import { Plus, Eye, Pencil, Trash2 } from "lucide-react"
import { api } from "@/lib/api"
import { useToast } from "@/hooks/use-toast"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"

export default function ListsPage() {
  const [lists, setLists] = useState<any[]>([])
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [isLoadingLists, setIsLoadingLists] = useState(true)
  const [searchUrl, setSearchUrl] = useState("")
  const [profileLimit, setProfileLimit] = useState(20)
  const [collectOnly, setCollectOnly] = useState(false)
  const [sendNote, setSendNote] = useState(false)
  const [noteText, setNoteText] = useState("")
  const [enabledSendersCount, setEnabledSendersCount] = useState(0)
  
  // Rename dialog state
  const [renameDialogOpen, setRenameDialogOpen] = useState(false)
  const [listToRename, setListToRename] = useState<any>(null)
  const [newListName, setNewListName] = useState("")
  const [isRenaming, setIsRenaming] = useState(false)
  
  // Delete dialog state
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const [listToDelete, setListToDelete] = useState<any>(null)
  const [isDeleting, setIsDeleting] = useState(false)
  
  const { toast } = useToast()

  // Fetch lists and senders on component mount
  useEffect(() => {
    fetchLists()
    fetchSenders()
  }, [])

  const fetchSenders = async () => {
    try {
      const sendersData = await api.getSenders()
      const enabledCount = sendersData.filter((s: any) => s.enabled === true).length
      setEnabledSendersCount(enabledCount)
    } catch (error) {
      console.error("Error fetching senders:", error)
      setEnabledSendersCount(0)
    }
  }

  // Helper function to determine if a list is processing
  const isListProcessing = (list: any): boolean => {
    // A list is considered processing if it has 0 profiles and was created recently (within last 10 minutes)
    if (list.profile_count !== 0) {
      return false
    }
    
    // Check if created_at is recent (within last 10 minutes)
    if (list.created_at) {
      const createdAt = new Date(list.created_at)
      const now = new Date()
      const diffMinutes = (now.getTime() - createdAt.getTime()) / (1000 * 60)
      return diffMinutes < 10 // Consider processing if created within last 10 minutes
    }
    
    return false
  }

  // Poll for list updates when there are processing lists
  useEffect(() => {
    const processingListIds = lists.filter((list) => isListProcessing(list)).map((l) => l.id)
    
    if (processingListIds.length === 0) {
      return // No processing lists, no need to poll
    }

    let isPolling = true
    const pollInterval = setInterval(async () => {
      if (!isPolling) return
      
      try {
        const updatedLists = await api.getLists()
        // Check if any of our processing lists are still processing
        const stillProcessing = updatedLists.some((list: any) => 
          processingListIds.includes(list.id) && isListProcessing(list)
        )
        
        // Only update lists when processing completes (profile_count > 0 or time elapsed)
        if (!stillProcessing) {
          console.log("[FRONTEND] List processing completed, refreshing lists")
          setLists(updatedLists)
          isPolling = false // Stop polling when done
        }
        // Don't update during processing - just keep showing "Processing"
      } catch (error) {
        console.error("Error polling lists:", error)
      }
    }, 5000) // Poll every 5 seconds (reduced frequency)

    return () => {
      isPolling = false
      clearInterval(pollInterval)
    }
  }, [lists.length]) // Only re-run when number of lists changes, not on every update

  const fetchLists = async () => {
    setIsLoadingLists(true)
    try {
      const listsData = await api.getLists()
      setLists(listsData)
    } catch (error) {
      toast({
        title: "Error",
        description: error instanceof Error ? error.message : "Failed to load lists",
        variant: "destructive",
      })
    } finally {
      setIsLoadingLists(false)
    }
  }

  const handleGenerateList = async () => {
    console.log("========================================")
    console.log("[FRONTEND] handleGenerateList called")
    console.log("========================================")
    
    if (!searchUrl.trim()) {
      console.log("[FRONTEND] ❌ Validation failed: searchUrl is empty")
      toast({
        title: "Error",
        description: "Please enter a LinkedIn search URL",
        variant: "destructive",
      })
      return
    }

    const requestData = {
      search_url: searchUrl,
      profile_limit: profileLimit,
      collect_only: collectOnly,
      send_note: sendNote,
      note_text: noteText,
    }

    console.log("[FRONTEND] ✓ Validation passed")
    console.log("[FRONTEND] Request data:", JSON.stringify(requestData, null, 2))
    console.log("[FRONTEND] About to call api.populateList()...")
    
    setIsLoading(true)
    try {
      console.log("[FRONTEND] 🚀 Calling api.populateList() NOW...")
      const result = await api.populateList(requestData)
      console.log("[FRONTEND] ✅ api.populateList() SUCCESS!")
      console.log("[FRONTEND] Response:", result)
      
      toast({
        title: "Success",
        description: "List generation started successfully",
      })
      setIsModalOpen(false)
      setSearchUrl("")
      setProfileLimit(20)
      setCollectOnly(false)
      setSendNote(false)
      setNoteText("")
      // Refresh the lists to show the new list with "Processing" status
      console.log("[FRONTEND] Refreshing lists...")
      await fetchLists()
      console.log("[FRONTEND] ✅ All done!")
    } catch (error) {
      console.log("[FRONTEND] ❌ ERROR in api.populateList():")
      console.error("[FRONTEND] Error details:", error)
      console.error("[FRONTEND] Error type:", error instanceof Error ? error.constructor.name : typeof error)
      console.error("[FRONTEND] Error message:", error instanceof Error ? error.message : String(error))
      
      toast({
        title: "Error",
        description: error instanceof Error ? error.message : "Failed to generate list",
        variant: "destructive",
      })
    } finally {
      setIsLoading(false)
      console.log("[FRONTEND] setIsLoading(false) called")
      console.log("========================================")
    }
  }

  const handleRenameClick = (list: any) => {
    setListToRename(list)
    setNewListName(list.name || "")
    setRenameDialogOpen(true)
  }

  const handleRename = async () => {
    if (!listToRename || !newListName.trim()) {
      toast({
        title: "Error",
        description: "Please enter a list name",
        variant: "destructive",
      })
      return
    }

    setIsRenaming(true)
    try {
      await api.updateList(listToRename.id, { name: newListName.trim() })
      toast({
        title: "Success",
        description: "List renamed successfully",
      })
      setRenameDialogOpen(false)
      setListToRename(null)
      setNewListName("")
      await fetchLists()
    } catch (error) {
      toast({
        title: "Error",
        description: error instanceof Error ? error.message : "Failed to rename list",
        variant: "destructive",
      })
    } finally {
      setIsRenaming(false)
    }
  }

  const handleDeleteClick = (list: any) => {
    setListToDelete(list)
    setDeleteDialogOpen(true)
  }

  const handleDelete = async () => {
    if (!listToDelete) return

    setIsDeleting(true)
    try {
      await api.deleteList(listToDelete.id)
      toast({
        title: "Success",
        description: "List deleted successfully",
      })
      setDeleteDialogOpen(false)
      setListToDelete(null)
      await fetchLists()
    } catch (error) {
      toast({
        title: "Error",
        description: error instanceof Error ? error.message : "Failed to delete list",
        variant: "destructive",
      })
    } finally {
      setIsDeleting(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Generate Lists</h1>
          <p className="text-muted-foreground mt-2">Manage your LinkedIn prospect lists for outreach campaigns</p>
        </div>
        <Button 
          onClick={() => setIsModalOpen(true)} 
          className="gap-2 shadow-sm"
          disabled={enabledSendersCount === 0}
          title={enabledSendersCount === 0 ? "No enabled senders available. Please enable at least one sender profile." : ""}
        >
          {enabledSendersCount === 0 ? (
            <>
              <Plus className="h-4 w-4" />
              No Enabled Sender
            </>
          ) : (
            <>
              <Plus className="h-4 w-4" />
              Generate New List
            </>
          )}
        </Button>
      </div>

      <Dialog open={isModalOpen} onOpenChange={setIsModalOpen}>
        <DialogContent className="sm:max-w-[525px]">
          <DialogHeader>
            <DialogTitle>Generate New List</DialogTitle>
            <DialogDescription>
              Enter a LinkedIn search URL to generate a list of prospects
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="searchUrl">LinkedIn Search URL</Label>
              <Input
                id="searchUrl"
                placeholder="https://www.linkedin.com/search/results/people/..."
                value={searchUrl}
                onChange={(e) => setSearchUrl(e.target.value)}
                required
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="profileLimit">Profile Limit</Label>
              <Input
                id="profileLimit"
                type="number"
                min="1"
                value={profileLimit}
                onChange={(e) => setProfileLimit(Number(e.target.value))}
              />
            </div>
            <div className="flex items-center space-x-2">
              <Checkbox
                id="collectOnly"
                checked={collectOnly}
                onCheckedChange={(checked) => setCollectOnly(checked === true)}
              />
              <Label htmlFor="collectOnly" className="cursor-pointer">
                Collect only (don't send invites)
              </Label>
            </div>
            <div className="flex items-center space-x-2">
              <Checkbox
                id="sendNote"
                checked={sendNote}
                onCheckedChange={(checked) => setSendNote(checked === true)}
              />
              <Label htmlFor="sendNote" className="cursor-pointer">
                Send note with connection request
              </Label>
            </div>
            {sendNote && (
              <div className="grid gap-2">
                <Label htmlFor="noteText">Connection Note</Label>
                <Textarea
                  id="noteText"
                  placeholder="Hi {{first_name}}, would love to connect!"
                  value={noteText}
                  onChange={(e) => setNoteText(e.target.value)}
                  rows={3}
                />
              </div>
            )}
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setIsModalOpen(false)}>
              Cancel
            </Button>
            <Button type="button" onClick={handleGenerateList} disabled={isLoading}>
              {isLoading ? "Generating..." : "Generate List"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Card className="shadow-sm">
        <CardHeader>
          <CardTitle>All Lists</CardTitle>
          <CardDescription>View and manage all your generated LinkedIn prospect lists</CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>List Name</TableHead>
                <TableHead>Profiles</TableHead>
                <TableHead>Created Date</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {isLoadingLists ? (
                <TableRow>
                  <TableCell colSpan={4} className="text-center text-muted-foreground">
                    Loading lists...
                  </TableCell>
                </TableRow>
              ) : lists.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={4} className="text-center text-muted-foreground">
                    No lists found. Generate your first list to get started.
                  </TableCell>
                </TableRow>
              ) : (
                lists.map((list) => (
                  <TableRow key={list.id}>
                    <TableCell className="font-medium">{list.name || "Unnamed List"}</TableCell>
                    <TableCell>
                      {isListProcessing(list) ? (
                        <Badge variant="default" className="bg-blue-500 hover:bg-blue-600">
                          Processing
                        </Badge>
                      ) : (
                        <Badge variant="secondary">{list.count || list.profile_count || 0} profiles</Badge>
                      )}
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {list.created_at
                        ? new Date(list.created_at).toLocaleDateString("en-US", {
                            year: "numeric",
                            month: "short",
                            day: "numeric",
                          })
                        : "N/A"}
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex items-center justify-end gap-2">
                        <Link href={`/lists/${list.id}`}>
                          <Button variant="outline" size="sm" className="gap-2 shadow-sm bg-transparent">
                            <Eye className="h-4 w-4" />
                            View
                          </Button>
                        </Link>
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button variant="outline" size="sm" className="shadow-sm bg-transparent">
                              <span className="sr-only">More options</span>
                              <svg
                                xmlns="http://www.w3.org/2000/svg"
                                width="16"
                                height="16"
                                viewBox="0 0 24 24"
                                fill="none"
                                stroke="currentColor"
                                strokeWidth="2"
                                strokeLinecap="round"
                                strokeLinejoin="round"
                              >
                                <circle cx="12" cy="12" r="1" />
                                <circle cx="12" cy="5" r="1" />
                                <circle cx="12" cy="19" r="1" />
                              </svg>
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            <DropdownMenuItem onClick={() => handleRenameClick(list)}>
                              <Pencil className="mr-2 h-4 w-4" />
                              Rename
                            </DropdownMenuItem>
                            <DropdownMenuItem
                              onClick={() => handleDeleteClick(list)}
                              className="text-destructive focus:text-destructive"
                            >
                              <Trash2 className="mr-2 h-4 w-4" />
                              Delete
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </div>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* Rename Dialog */}
      <Dialog open={renameDialogOpen} onOpenChange={setRenameDialogOpen}>
        <DialogContent className="sm:max-w-[425px]">
          <DialogHeader>
            <DialogTitle>Rename List</DialogTitle>
            <DialogDescription>Enter a new name for this list.</DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="newListName">List Name</Label>
              <Input
                id="newListName"
                value={newListName}
                onChange={(e) => setNewListName(e.target.value)}
                placeholder="Enter list name"
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
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
            <Button type="button" onClick={handleRename} disabled={isRenaming || !newListName.trim()}>
              {isRenaming ? "Renaming..." : "Rename"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Are you sure?</AlertDialogTitle>
            <AlertDialogDescription>
              This action cannot be undone. This will delete the list "{listToDelete?.name}". 
              The profiles associated with this list will also be deleted.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isDeleting}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDelete}
              disabled={isDeleting}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {isDeleting ? "Deleting..." : "Delete"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
