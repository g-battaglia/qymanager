import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"

export function WarningList({ warnings }: { warnings: string[] }) {
  if (warnings.length === 0) {
    return <p className="text-sm text-muted-foreground">No warnings.</p>
  }
  return (
    <div>
      <p className="mb-2 text-sm">Conversion warnings:</p>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Warning</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {warnings.map((w, i) => (
            <TableRow key={i}>
              <TableCell className="font-mono text-xs">{w}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}
