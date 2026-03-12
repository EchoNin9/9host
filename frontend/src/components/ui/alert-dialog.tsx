"use client"

import * as React from "react"
import {
  AlertDialog as AlertDialogRoot,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent as AlertDialogContentPrimitive,
  AlertDialogDescription,
  AlertDialogOverlay,
  AlertDialogPortal,
  AlertDialogTitle,
  AlertDialogTrigger as AlertDialogTriggerPrimitive,
} from "@radix-ui/react-alert-dialog"

import { cn } from "@/lib/utils"
import { buttonVariants } from "@/lib/button-variants"

function AlertDialog(props: React.ComponentProps<typeof AlertDialogRoot>) {
  return <AlertDialogRoot {...props} />
}

function AlertDialogTrigger(
  props: React.ComponentProps<typeof AlertDialogTriggerPrimitive>
) {
  return <AlertDialogTriggerPrimitive {...props} />
}

function AlertDialogContent({
  className,
  ...props
}: React.ComponentProps<typeof AlertDialogContentPrimitive>) {
  return (
    <AlertDialogPortal>
      <AlertDialogOverlay className="fixed inset-0 z-50 bg-black/50 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0" />
      <AlertDialogContentPrimitive
        className={cn(
          "fixed left-[50%] top-[50%] z-50 grid w-full max-w-lg translate-x-[-50%] translate-y-[-50%] gap-4 border bg-background p-6 shadow-lg duration-200 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95 data-[state=closed]:slide-out-to-left-1/2 data-[state=closed]:slide-out-to-top-[48%] data-[state=open]:slide-in-from-left-1/2 data-[state=open]:slide-in-from-top-[48%] sm:rounded-lg",
          className
        )}
        {...props}
      />
    </AlertDialogPortal>
  )
}

function AlertDialogHeader({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "flex flex-col space-y-2 text-center sm:text-left",
        className
      )}
      {...props}
    />
  )
}

function AlertDialogFooter({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "flex flex-col-reverse sm:flex-row sm:justify-end sm:gap-2",
        className
      )}
      {...props}
    />
  )
}

const StyledAlertDialogCancel = React.forwardRef<
  HTMLButtonElement,
  React.ComponentProps<typeof AlertDialogCancel>
>(({ className, ...props }, ref) => (
  <AlertDialogCancel
    ref={ref}
    className={cn(buttonVariants({ variant: "outline" }), "mt-2 sm:mt-0", className)}
    {...props}
  />
))
StyledAlertDialogCancel.displayName = "AlertDialogCancel"

const StyledAlertDialogAction = React.forwardRef<
  HTMLButtonElement,
  React.ComponentProps<typeof AlertDialogAction>
>(({ className, ...props }, ref) => (
  <AlertDialogAction
    ref={ref}
    className={cn(buttonVariants(), className)}
    {...props}
  />
))
StyledAlertDialogAction.displayName = "AlertDialogAction"

export {
  AlertDialog,
  AlertDialogTrigger,
  AlertDialogContent,
  AlertDialogHeader,
  AlertDialogFooter,
  AlertDialogTitle,
  AlertDialogDescription,
  StyledAlertDialogAction as AlertDialogAction,
  StyledAlertDialogCancel as AlertDialogCancel,
}
