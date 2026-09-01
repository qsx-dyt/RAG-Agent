    import { message as antMessage } from "antd";
    import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
    import UploadDropzone from "../components/UploadDropzone";
    import DocumentTable, { DocumentRow } from "../components/DocumentTable";
    import { listDocuments, uploadDocuments, deleteDocument } from "../api/client";

    export default function DocumentsPage() {
      const qc = useQueryClient();
      const docsQuery = useQuery({ queryKey: ["documents"], queryFn: listDocuments });
      const upload = useMutation({
        mutationFn: uploadDocuments,
        onSuccess: () => { qc.invalidateQueries({ queryKey: ["documents"] }); antMessage.success("上传完成"); },
        onError: (e: Error) => antMessage.error(e.message),
      });
      const del = useMutation({
        mutationFn: deleteDocument,
        onSuccess: () => { qc.invalidateQueries({ queryKey: ["documents"] }); antMessage.success("已删除"); },
      });
      const rows = (docsQuery.data ?? []) as unknown as DocumentRow[];
      return (
        <div style={{ maxWidth: 960, margin: "0 auto" }}>
          <UploadDropzone onUpload={(files) => upload.mutate(files)} />
          <div style={{ marginTop: 16 }}>
            <DocumentTable data={rows} onDelete={(id) => del.mutate(id)} />
          </div>
        </div>
      );
    }
