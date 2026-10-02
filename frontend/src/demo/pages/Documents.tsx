import { sampleDocuments } from "../data";

export default function Documents() {
  return (
    <section className="demo-page">
      <div className="demo-page-head">
        <p className="demo-kicker">Tài liệu dạy học</p>
        <h1>Nguồn tham khảo mẫu</h1>
        <p>
          Trong sản phẩm đầy đủ, giáo viên có thể dùng tài liệu của mình khi
          soạn đề. Danh sách dưới đây chỉ để minh hoạ giao diện.
        </p>
      </div>
      <div className="demo-list">
        {sampleDocuments.map((document) => (
          <div className="demo-document-row" key={document.name}>
            <span className="demo-row-icon">▤</span>
            <span>
              <strong>{document.name}</strong>
              <small>{document.note}</small>
            </span>
            <span className="demo-file-type">{document.kind}</span>
          </div>
        ))}
      </div>
      <div className="demo-tip">
        <span>✳</span>
        <p>Bản demo không nhận tệp tải lên và không gửi tài liệu ra máy chủ.</p>
      </div>
    </section>
  );
}
