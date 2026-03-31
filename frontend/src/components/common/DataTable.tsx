interface Props {
  headers: string[]
  rows: string[][]
  maxRows?: number
}

export function DataTable({ headers, rows, maxRows = 5 }: Props) {
  const visible = rows.slice(0, maxRows)
  return (
    <div className="overflow-x-auto rounded-lg border border-gray-200">
      <table className="min-w-full divide-y divide-gray-200 text-xs">
        <thead className="bg-gray-50">
          <tr>
            {headers.map((h) => (
              <th
                key={h}
                className="px-3 py-2 text-left font-medium text-gray-500 uppercase tracking-wide whitespace-nowrap"
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100 bg-white">
          {visible.map((row, i) => (
            <tr key={i}>
              {row.map((cell, j) => (
                <td key={j} className="px-3 py-2 text-gray-700 whitespace-nowrap max-w-[120px] truncate">
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {rows.length > maxRows && (
        <p className="px-3 py-2 text-xs text-gray-400 bg-gray-50 border-t border-gray-200">
          Showing {maxRows} of {rows.length} rows
        </p>
      )}
    </div>
  )
}
