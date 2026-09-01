import { BrowserRouter, Routes, Route, Link } from "react-router-dom";
import { Layout, Menu } from "antd";
import ChatPage from "./pages/ChatPage";
import DocumentsPage from "./pages/DocumentsPage";

export default function App() {
  return (
    <BrowserRouter>
      <Layout style={{ minHeight: "100vh" }}>
        <Layout.Header>
          <Menu theme="dark" mode="horizontal" selectable={false}>
            <Menu.Item key="brand" style={{ fontWeight: 700, color: "#fff" }}>
              Enterprise RAG Agent
            </Menu.Item>
            <Menu.Item key="chat"><Link to="/">聊天</Link></Menu.Item>
            <Menu.Item key="docs"><Link to="/documents">文档管理</Link></Menu.Item>
          </Menu>
        </Layout.Header>
        <Layout.Content style={{ padding: 24 }}>
          <Routes>
            <Route path="/" element={<ChatPage />} />
            <Route path="/documents" element={<DocumentsPage />} />
          </Routes>
        </Layout.Content>
      </Layout>
    </BrowserRouter>
  );
}
