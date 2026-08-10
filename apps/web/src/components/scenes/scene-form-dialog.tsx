"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import {
  KEYFRAME_CHOICES,
  LOCATIONS,
  SENSOR_SUITES,
  TIMES_OF_DAY,
  WEATHERS,
} from "@/lib/scene-fields";
import { useCreateScene, useUpdateScene } from "@/lib/queries";
import type { SceneSummary } from "@nuscenes-sensor-data-lake/shared";

const baseSchema = {
  name: z
    .string()
    .min(2, "Name must be at least 2 characters")
    .max(64, "Name must be 64 characters or fewer"),
  description: z.string().max(280, "Description must be 280 characters or fewer"),
  location: z.enum([
    "boston-seaport",
    "singapore-onenorth",
    "singapore-queenstown",
    "singapore-hollandvillage",
  ]),
  timeOfDay: z.enum(["day", "night"]),
  weather: z.enum(["clear", "rain"]),
};

const createSchema = z.object({
  ...baseSchema,
  keyframes: z.enum(["3", "5", "10"]),
  sensorSuite: z.enum(["full", "camera+lidar"]),
});
const editSchema = z.object(baseSchema);

type CreateValues = z.infer<typeof createSchema>;
type EditValues = z.infer<typeof editSchema>;

const CREATE_DEFAULTS: CreateValues = {
  name: "",
  description: "",
  location: "boston-seaport",
  timeOfDay: "day",
  weather: "clear",
  keyframes: "5",
  sensorSuite: "full",
};

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  scene?: SceneSummary; // present -> edit mode; absent -> create mode
}

export function SceneFormDialog({ open, onOpenChange, scene }: Props) {
  const isEdit = scene !== undefined;
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{isEdit ? "Edit scene" : "New scene"}</DialogTitle>
          <DialogDescription>
            {isEdit
              ? "Update this scene's metadata. The nuScenes tables in B2 are rewritten to match."
              : "Synthesize a referentially-valid nuScenes scene and ingest its sensor blobs + annotation tables to Backblaze B2."}
          </DialogDescription>
        </DialogHeader>
        {isEdit ? (
          <EditForm scene={scene} onDone={() => onOpenChange(false)} />
        ) : (
          <CreateForm onDone={() => onOpenChange(false)} />
        )}
      </DialogContent>
    </Dialog>
  );
}

function LocationField({ field }: { field: { value: string; onChange: (v: string) => void } }) {
  return (
    <FormItem>
      <FormLabel>Location</FormLabel>
      <Select onValueChange={field.onChange} value={field.value}>
        <FormControl>
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
        </FormControl>
        <SelectContent>
          {LOCATIONS.map((o) => (
            <SelectItem key={o.value} value={o.value}>
              {o.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      <FormMessage />
    </FormItem>
  );
}

function WeatherField({ field }: { field: { value: string; onChange: (v: string) => void } }) {
  return (
    <FormItem>
      <FormLabel>Weather</FormLabel>
      <Select onValueChange={field.onChange} value={field.value}>
        <FormControl>
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
        </FormControl>
        <SelectContent>
          {WEATHERS.map((o) => (
            <SelectItem key={o.value} value={o.value}>
              {o.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      <FormMessage />
    </FormItem>
  );
}

function TimeOfDayField({ field }: { field: { value: string; onChange: (v: string) => void } }) {
  return (
    <FormItem>
      <FormLabel>Time of day</FormLabel>
      <FormControl>
        <RadioGroup onValueChange={field.onChange} value={field.value} className="flex gap-6">
          {TIMES_OF_DAY.map((o) => (
            <label key={o.value} className="flex items-center gap-2 text-sm cursor-pointer">
              <RadioGroupItem value={o.value} />
              {o.label}
            </label>
          ))}
        </RadioGroup>
      </FormControl>
      <FormMessage />
    </FormItem>
  );
}

function CreateForm({ onDone }: { onDone: () => void }) {
  const router = useRouter();
  const form = useForm<CreateValues>({
    resolver: zodResolver(createSchema),
    defaultValues: CREATE_DEFAULTS,
  });
  const create = useCreateScene();

  // handleSubmit only calls this after client validation passes, so closing the
  // dialog here is safe. We close immediately (no modal trapping navigation
  // during the multi-second ingest) and track progress with a non-blocking
  // sonner loading toast. mutateAsync's promise settles independently of the
  // now-unmounted form, so the toast always resolves — unlike mutate()'s
  // per-call callbacks, which React Query drops once the observer unmounts.
  const onSubmit = (values: CreateValues) => {
    const id = toast.loading(
      `Ingesting ${values.name} to B2 — synthesizing sensors & uploading blobs…`,
    );
    onDone();
    create
      .mutateAsync({
        name: values.name,
        description: values.description,
        location: values.location,
        time_of_day: values.timeOfDay,
        weather: values.weather,
        keyframes: Number(values.keyframes),
        sensor_suite: values.sensorSuite,
      })
      .then((scene) => {
        toast.success("Scene ingested to B2", {
          id,
          description: `${scene.name} — ${scene.blob_count} sensor blobs under nuscenes/${scene.token}/`,
          action: {
            label: "Open scene",
            onClick: () => router.push(`/scenes/${scene.token}`),
          },
        });
        // Auto-chain to the new scene's Serve panel so the primary flow lands
        // on the payoff without hunting for the (delayed, auto-dismissing)
        // toast action. Guarded: only push if the user is still on the scenes
        // list — if they navigated elsewhere during the multi-second ingest,
        // don't yank them; the toast's "Open scene" action is the fallback.
        if (window.location.pathname === "/scenes") {
          router.push(`/scenes/${scene.token}`);
        }
      })
      .catch((error: Error) => {
        toast.error("Ingest failed", { id, description: error.message });
      });
  };

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
        <FormField
          control={form.control}
          name="name"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Name</FormLabel>
              <FormControl>
                <Input placeholder="scene-boston-01" {...field} />
              </FormControl>
              <FormDescription>
                Defaults below produce a sound demo scene you can index immediately.
              </FormDescription>
              <FormMessage />
            </FormItem>
          )}
        />
        <FormField
          control={form.control}
          name="description"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Description</FormLabel>
              <FormControl>
                <Textarea placeholder="Optional notes about this capture" className="resize-none" {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <div className="grid gap-4 sm:grid-cols-2">
          <FormField control={form.control} name="location" render={({ field }) => <LocationField field={field} />} />
          <FormField control={form.control} name="weather" render={({ field }) => <WeatherField field={field} />} />
        </div>
        <FormField control={form.control} name="timeOfDay" render={({ field }) => <TimeOfDayField field={field} />} />
        <div className="grid gap-4 sm:grid-cols-2">
          <FormField
            control={form.control}
            name="keyframes"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Keyframes</FormLabel>
                <Select onValueChange={field.onChange} value={field.value}>
                  <FormControl>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                  </FormControl>
                  <SelectContent>
                    {KEYFRAME_CHOICES.map((k) => (
                      <SelectItem key={k} value={String(k)}>
                        {k} keyframes
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={form.control}
            name="sensorSuite"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Sensor suite</FormLabel>
                <Select onValueChange={field.onChange} value={field.value}>
                  <FormControl>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                  </FormControl>
                  <SelectContent>
                    {SENSOR_SUITES.map((o) => (
                      <SelectItem key={o.value} value={o.value}>
                        {o.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <FormMessage />
              </FormItem>
            )}
          />
        </div>
        <DialogFooter>
          <Button type="button" variant="outline" onClick={onDone}>
            Cancel
          </Button>
          <Button type="submit" disabled={create.isPending}>
            {create.isPending ? "Ingesting..." : "Create scene"}
          </Button>
        </DialogFooter>
      </form>
    </Form>
  );
}

function EditForm({ scene, onDone }: { scene: SceneSummary; onDone: () => void }) {
  const form = useForm<EditValues>({
    resolver: zodResolver(editSchema),
    defaultValues: {
      name: scene.name,
      description: scene.description,
      location: scene.location as EditValues["location"],
      timeOfDay: scene.time_of_day as EditValues["timeOfDay"],
      weather: scene.weather as EditValues["weather"],
    },
  });
  const update = useUpdateScene(scene.token);

  useEffect(() => {
    form.reset({
      name: scene.name,
      description: scene.description,
      location: scene.location as EditValues["location"],
      timeOfDay: scene.time_of_day as EditValues["timeOfDay"],
      weather: scene.weather as EditValues["weather"],
    });
  }, [form, scene]);

  const onSubmit = (values: EditValues) => {
    update.mutate(
      {
        name: values.name,
        description: values.description,
        location: values.location,
        time_of_day: values.timeOfDay,
        weather: values.weather,
      },
      {
        onSuccess: () => {
          toast.success("Scene updated");
          onDone();
        },
        onError: (error) => toast.error("Update failed", { description: error.message }),
      },
    );
  };

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
        <FormField
          control={form.control}
          name="name"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Name</FormLabel>
              <FormControl>
                <Input {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <FormField
          control={form.control}
          name="description"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Description</FormLabel>
              <FormControl>
                <Textarea className="resize-none" {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <div className="grid gap-4 sm:grid-cols-2">
          <FormField control={form.control} name="location" render={({ field }) => <LocationField field={field} />} />
          <FormField control={form.control} name="weather" render={({ field }) => <WeatherField field={field} />} />
        </div>
        <FormField control={form.control} name="timeOfDay" render={({ field }) => <TimeOfDayField field={field} />} />
        <DialogFooter>
          <Button type="button" variant="outline" onClick={onDone}>
            Cancel
          </Button>
          <Button type="submit" disabled={update.isPending}>
            {update.isPending ? "Saving..." : "Save changes"}
          </Button>
        </DialogFooter>
      </form>
    </Form>
  );
}

// Keeps a single stateful open/close entry point for pages that want a button
// wired to the dialog.
export function useSceneDialog() {
  const [open, setOpen] = useState(false);
  return { open, setOpen };
}
