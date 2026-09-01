import { Upload } from "antd";
import { InboxOutlined } from "@ant-design/icons";

export default function UploadDropzone({ onUpload }: { onUpload: (files: File[]) => void }) {
  return (
    <Upload.Dragger
      multiple
      accept=".pdf,.md,.markdown"
      beforeUpload={() => false}
      onChange={({ fileList }) => {
        const files = fileList.map((f) => f.originFileObj).filter(Boolean) as File[];
        if (files.length) onUpload(files);
      }}
    >
      <p className="ant-upload-drag-icon"><InboxOutlined /></p>
      <p>点击或拖拽上传 PDF / Markdown 文档</p>
    </Upload.Dragger>
  );
}
