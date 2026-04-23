import { Uploader } from "@/components/Uploader"

export default function Dashboard() {
  return (
    <div className="max-w-4xl mx-auto p-8">
      <h1 className="text-3xl font-bold mb-6">QYConv</h1>
      <p className="mb-4 text-muted-foreground">
        Yamaha QY70 / QY700 editor. Upload a file to get started.
      </p>
      <Uploader />
    </div>
  )
}
