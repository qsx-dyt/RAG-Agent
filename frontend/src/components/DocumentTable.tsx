import { Table, Button, Modal, Tag } from "antd";

export interface DocumentRow {
  id: string;
  title: string;
  source_type: string;
  status: string;
  chunk_count?: number;
  created_at: string;
}

const statusColor: Record<string, string> = { ready: "green", processing: "blue", failed: "red" };

export default function DocumentTable({ data, onDelete }: {
  data: DocumentRow[];
  onDelete: (id: string) => void;
}) {
  const columns = [
    { title: "标题", dataIndex: "title" },
    { title: "类型", dataIndex: "source_type", render: (v: string) => v === "pdf" ? "PDF" : "Markdown" },
    { title: "状态", dataIndex: "status",
      render: (v: string) => <Tag color={statusColor[v] ?? "default"}>{v}</Tag> },
    { title: "切片数", dataIndex: "chunk_count" },
    { title: "创建时间", dataIndex: "created_at", render: (v: string) => v?.slice(0, 19).replace("T", " ") },
    { title: "操作", key: "op",
      render: (_: unknown, row: DocumentRow) => (
        <Button danger size="small" onClick={() => {
          Modal.confirm({
            title: "删除文档",
            content: `确定删除「${row.title}」吗?相关切片与向量将一并清理。`,
            onOk: () => onDelete(row.id),
          });
        }}>删除</Button>
      ) },
  ];
  return <Table rowKey="id" dataSource={data} columns={columns} pagination={false} />;
}
