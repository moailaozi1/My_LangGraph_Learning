// ApprovalCard.tsx
import { useState } from "react";
import type { InterruptPayload } from "./api";

interface Props {
  interrupt: InterruptPayload;
  onRespond: (decision: Record<string, unknown>) => void;
}

export function ApprovalCard({ interrupt, onRespond }: Props) {
  const [rejectReason, setRejectReason] = useState("");
  const [mode, setMode] = useState<"view" | "reject" | "edit">("view");
  const [editedBody, setEditedBody] = useState(
    String(interrupt.args.body ?? "")
  );

  return (
    <div style={{
      border: "2px solid #f59e0b",
      borderRadius: 12,
      padding: 20,
      margin: "16px 0",
      background: "#fffbeb",
    }}>
      <div style={{ fontWeight: 700, fontSize: 16, marginBottom: 12 }}>
        ⏸ 待审批操作
      </div>
      <div style={{ marginBottom: 8 }}>
        <strong>操作：</strong> {interrupt.action}
      </div>
      <div style={{ marginBottom: 8 }}>
        <strong>描述：</strong> {interrupt.description}
      </div>
      <div style={{
        background: "#fff",
        border: "1px solid #e5e7eb",
        borderRadius: 8,
        padding: 12,
        marginBottom: 16,
        whiteSpace: "pre-wrap",
        fontFamily: "monospace",
        fontSize: 13,
      }}>
        <div><strong>收件人：</strong> {String(interrupt.args.to)}</div>
        <div><strong>主题：</strong> {String(interrupt.args.subject)}</div>
        <hr />
        {mode === "edit" ? (
          <textarea
            value={editedBody}
            onChange={(e) => setEditedBody(e.target.value)}
            rows={6}
            style={{ width: "100%", fontFamily: "monospace" }}
          />
        ) : (
          <div>{String(interrupt.args.body)}</div>
        )}
      </div>

      {mode === "reject" && (
        <textarea
          placeholder="请输入拒绝原因..."
          value={rejectReason}
          onChange={(e) => setRejectReason(e.target.value)}
          rows={2}
          style={{ width: "100%", marginBottom: 12 }}
        />
      )}

      <div style={{ display: "flex", gap: 8 }}>
        {mode === "view" && (
          <>
            <button
              onClick={() => onRespond({ type: "approve" })}
              style={{ background: "#22c55e", color: "#fff", padding: "8px 20px", border: "none", borderRadius: 6, cursor: "pointer" }}
            >
              ✅ 批准
            </button>
            <button
              onClick={() => setMode("reject")}
              style={{ background: "#ef4444", color: "#fff", padding: "8px 20px", border: "none", borderRadius: 6, cursor: "pointer" }}
            >
              ❌ 拒绝
            </button>
            <button
              onClick={() => setMode("edit")}
              style={{ background: "#3b82f6", color: "#fff", padding: "8px 20px", border: "none", borderRadius: 6, cursor: "pointer" }}
            >
              ✏️ 编辑后批准
            </button>
          </>
        )}

        {mode === "reject" && (
          <>
            <button
              onClick={() => onRespond({ type: "reject", message: rejectReason })}
              style={{ background: "#ef4444", color: "#fff", padding: "8px 20px", border: "none", borderRadius: 6, cursor: "pointer" }}
            >
              确认拒绝
            </button>
            <button
              onClick={() => setMode("view")}
              style={{ background: "#9ca3af", color: "#fff", padding: "8px 20px", border: "none", borderRadius: 6, cursor: "pointer" }}
            >
              取消
            </button>
          </>
        )}

        {mode === "edit" && (
          <>
            <button
              onClick={() =>
                onRespond({
                  type: "edit",
                  editedAction: {
                    name: interrupt.action,
                    args: { ...interrupt.args, body: editedBody },
                  },
                })
              }
              style={{ background: "#3b82f6", color: "#fff", padding: "8px 20px", border: "none", borderRadius: 6, cursor: "pointer" }}
            >
              确认编辑并批准
            </button>
            <button
              onClick={() => setMode("view")}
              style={{ background: "#9ca3af", color: "#fff", padding: "8px 20px", border: "none", borderRadius: 6, cursor: "pointer" }}
            >
              取消
            </button>
          </>
        )}
      </div>
    </div>
  );
}