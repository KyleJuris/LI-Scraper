"use client"

import type React from "react"

import { useState, useEffect } from "react"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Checkbox } from "@/components/ui/checkbox"
import { ScrollArea } from "@/components/ui/scroll-area"
import { api } from "@/lib/api"

interface CreateCampaignModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onSubmit: (data: { name: string; listIds: string[]; profileId: string; message: string }) => void
  disabled?: boolean
}

export function CreateCampaignModal({ open, onOpenChange, onSubmit, disabled }: CreateCampaignModalProps) {
  const [name, setName] = useState("")
  const [listIds, setListIds] = useState<string[]>([])
  const [profileId, setProfileId] = useState("")
  const [message, setMessage] = useState("")
  const [lists, setLists] = useState<any[]>([])
  const [senderProfiles, setSenderProfiles] = useState<any[]>([])
  const [isLoadingData, setIsLoadingData] = useState(false)

  // Fetch lists and senders when modal opens
  useEffect(() => {
    if (open) {
      fetchData()
    } else {
      // Reset form when modal closes
      setName("")
      setListIds([])
      setProfileId("")
      setMessage("")
    }
  }, [open])

  const fetchData = async () => {
    setIsLoadingData(true)
    try {
      const [listsData, sendersData] = await Promise.all([
        api.getLists(),
        api.getSenders(),
      ])
      setLists(listsData)
      // Only show enabled senders
      const enabledSenders = sendersData.filter((s: any) => s.enabled === true)
      setSenderProfiles(enabledSenders)
    } catch (error) {
      console.error("Error fetching data:", error)
      setLists([])
      setSenderProfiles([])
    } finally {
      setIsLoadingData(false)
    }
  }

  const handleToggleList = (listId: string) => {
    setListIds((prev) => {
      if (prev.includes(listId)) {
        return prev.filter((id) => id !== listId)
      } else {
        return [...prev, listId]
      }
    })
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (name && listIds.length > 0 && profileId && message) {
      onSubmit({ name, listIds, profileId, message })
      // Reset form
      setName("")
      setListIds([])
      setProfileId("")
      setMessage("")
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[525px]">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>Create New Campaign</DialogTitle>
            <DialogDescription>
              Set up a new LinkedIn outreach campaign. Select a sender profile, one or more lists, and customize your message
              template.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="name">Campaign Name</Label>
              <Input
                id="name"
                placeholder="Q1 Outreach Campaign"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="profile">Sender Profile</Label>
              <Select value={profileId} onValueChange={setProfileId} required disabled={isLoadingData || senderProfiles.length === 0}>
                <SelectTrigger id="profile">
                  <SelectValue placeholder={isLoadingData ? "Loading..." : senderProfiles.length === 0 ? "No enabled senders" : "Choose sender profile"} />
                </SelectTrigger>
                <SelectContent>
                  {isLoadingData ? (
                    <div className="px-2 py-1.5 text-sm text-muted-foreground">Loading...</div>
                  ) : senderProfiles.length === 0 ? (
                    <div className="px-2 py-1.5 text-sm text-muted-foreground">No enabled sender profiles available</div>
                  ) : (
                    senderProfiles.map((profile) => (
                      <SelectItem key={profile.id} value={profile.id.toString()}>
                        {profile.name || profile.id}
                      </SelectItem>
                    ))
                  )}
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="list">Select Lists</Label>
              {isLoadingData ? (
                <div className="px-2 py-1.5 text-sm text-muted-foreground">Loading...</div>
              ) : lists.length === 0 ? (
                <div className="px-2 py-1.5 text-sm text-muted-foreground">No lists available</div>
              ) : (
                <ScrollArea className="h-[200px] rounded-md border p-4">
                  <div className="grid gap-3">
                    {lists.map((list) => {
                      const listIdStr = list.id.toString()
                      const isChecked = listIds.includes(listIdStr)
                      return (
                        <div key={list.id} className="flex items-center space-x-2">
                          <Checkbox
                            id={`list-${list.id}`}
                            checked={isChecked}
                            onCheckedChange={() => handleToggleList(listIdStr)}
                          />
                          <label
                            htmlFor={`list-${list.id}`}
                            className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70 cursor-pointer flex-1"
                          >
                            {list.name}
                          </label>
                        </div>
                      )
                    })}
                  </div>
                </ScrollArea>
              )}
              {listIds.length > 0 && (
                <p className="text-xs text-muted-foreground">{listIds.length} list{listIds.length !== 1 ? "s" : ""} selected</p>
              )}
            </div>
            <div className="grid gap-2">
              <Label htmlFor="message">Message Template</Label>
              <Textarea
                id="message"
                placeholder="Hey! I noticed your work on..."
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                rows={5}
                required
              />
            </div>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" className="shadow-sm" disabled={disabled}>
              {disabled ? "Starting..." : "Start Campaign"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
