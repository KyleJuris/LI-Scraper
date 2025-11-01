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

interface AddProfileModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onSubmit: (data: { name: string; storage_state?: string }) => void
}

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

export function AddProfileModal({ open, onOpenChange, onSubmit }: AddProfileModalProps) {
  const [name, setName] = useState("")
  const [storageState, setStorageState] = useState("")

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (name.trim()) {
      onSubmit({ 
        name: name.trim(), 
        storage_state: storageState.trim() || undefined 
      })
      // Reset form
      setName("")
      setStorageState("")
    }
  }

  // Reset form when modal closes
  useEffect(() => {
    if (!open) {
      setName("")
      setStorageState("")
    }
  }, [open])

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[600px] max-h-[90vh] overflow-y-auto">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>Add Sender Profile</DialogTitle>
            <DialogDescription>
              Add a LinkedIn account that will be used to send messages in your campaigns.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="name">Sender Name</Label>
              <Input
                id="name"
                placeholder="LinkedIn Account"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
              />
              <p className="text-xs text-muted-foreground">
                A unique ID will be automatically generated for this sender.
              </p>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="storageState">Storage State (Cookies JSON)</Label>
              <Textarea
                id="storageState"
                value={storageState}
                onChange={(e) => setStorageState(e.target.value)}
                placeholder={STORAGE_STATE_SAMPLE}
                rows={12}
                className="font-mono text-sm"
              />
              <p className="text-xs text-muted-foreground">
                Paste the storage state JSON from Playwright. This contains cookies and session data for authentication.
              </p>
            </div>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" className="shadow-sm">
              Add Profile
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

