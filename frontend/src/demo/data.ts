export type DemoQuestion = {
  id: string;
  type: "multiple_choice" | "true_false" | "short_answer" | "essay";
  level: "Nhận biết" | "Thông hiểu" | "Vận dụng";
  prompt: string;
  options?: string[];
  answer: string;
  explanation: string;
  approved: boolean;
  revision: number;
};

export type DemoExam = {
  id: string;
  title: string;
  grade: number;
  term: string;
  duration: number;
  topic: string;
  createdAt: string;
  questions: DemoQuestion[];
};

const samples: Record<
  number,
  Omit<DemoQuestion, "id" | "approved" | "revision">[]
> = {
  6: [
    {
      type: "multiple_choice",
      level: "Nhận biết",
      prompt: "Dụng cụ nào dùng để đo thể tích chất lỏng?",
      options: ["Ống đong", "Nhiệt kế", "Cân điện tử", "Thước kẻ"],
      answer: "A. Ống đong",
      explanation: "Ống đong có vạch chia để đọc thể tích chất lỏng.",
    },
    {
      type: "true_false",
      level: "Thông hiểu",
      prompt:
        "Nước tinh khiết sôi ở 100 °C trong điều kiện áp suất tiêu chuẩn.",
      answer: "Đúng",
      explanation:
        "Nhiệt độ sôi của nước thay đổi theo áp suất; ở áp suất tiêu chuẩn là 100 °C.",
    },
    {
      type: "short_answer",
      level: "Thông hiểu",
      prompt: "Hãy nêu hai tính chất vật lí của oxygen.",
      answer: "Oxygen là chất khí, không màu, ít tan trong nước.",
      explanation: "Có thể nêu hai trong ba tính chất trên.",
    },
    {
      type: "essay",
      level: "Vận dụng",
      prompt:
        "Một học sinh muốn tách cát ra khỏi hỗn hợp cát và nước. Em hãy nêu cách làm và giải thích.",
      answer:
        "Dùng phương pháp lọc. Cát không tan và bị giữ trên giấy lọc, nước đi qua giấy lọc.",
      explanation:
        "Nêu đúng phương pháp và giải thích theo kích thước hạt, tính không tan.",
    },
  ],
  7: [
    {
      type: "multiple_choice",
      level: "Nhận biết",
      prompt: "Nguyên tử được tạo thành từ những hạt nào?",
      options: [
        "Proton, neutron và electron",
        "Chỉ proton",
        "Chỉ electron",
        "Phân tử và hợp chất",
      ],
      answer: "A. Proton, neutron và electron",
      explanation:
        "Hạt nhân gồm proton và neutron; electron chuyển động xung quanh hạt nhân.",
    },
    {
      type: "true_false",
      level: "Thông hiểu",
      prompt: "Trong một nguyên tử trung hoà điện, số proton bằng số electron.",
      answer: "Đúng",
      explanation:
        "Proton mang điện tích dương, electron mang điện tích âm cùng độ lớn; số lượng bằng nhau giúp nguyên tử trung hoà điện.",
    },
    {
      type: "short_answer",
      level: "Thông hiểu",
      prompt: "Vì sao cây xanh cần ánh sáng để quang hợp?",
      answer: "Ánh sáng cung cấp năng lượng cho quá trình quang hợp.",
      explanation:
        "Cây sử dụng năng lượng ánh sáng để tạo chất hữu cơ từ carbon dioxide và nước.",
    },
    {
      type: "essay",
      level: "Vận dụng",
      prompt:
        "Đề xuất một cách chăm sóc cây xanh giúp cây sinh trưởng tốt và giải thích tác dụng.",
      answer:
        "Ví dụ: đặt cây ở nơi có ánh sáng phù hợp để cây quang hợp, tạo chất hữu cơ phục vụ sinh trưởng.",
      explanation:
        "Chấp nhận giải pháp hợp lí về ánh sáng, nước hoặc dinh dưỡng có giải thích tác dụng.",
    },
  ],
  8: [
    {
      type: "multiple_choice",
      level: "Nhận biết",
      prompt: "Đơn vị đo áp suất trong hệ SI là gì?",
      options: ["Pascal (Pa)", "Newton (N)", "Joule (J)", "Watt (W)"],
      answer: "A. Pascal (Pa)",
      explanation:
        "Áp suất bằng áp lực chia cho diện tích bị ép, có đơn vị N/m² hay Pa.",
    },
    {
      type: "true_false",
      level: "Thông hiểu",
      prompt: "Khi diện tích bị ép giảm mà áp lực không đổi, áp suất tăng.",
      answer: "Đúng",
      explanation:
        "Theo công thức p = F/S, nếu S giảm và F không đổi thì p tăng.",
    },
    {
      type: "short_answer",
      level: "Vận dụng",
      prompt: "Một lực 200 N tác dụng đều lên diện tích 0,5 m². Tính áp suất.",
      answer: "p = F/S = 200/0,5 = 400 Pa.",
      explanation: "Đổi đúng đơn vị và áp dụng công thức p = F/S.",
    },
    {
      type: "essay",
      level: "Vận dụng",
      prompt:
        "Vì sao xe tăng dùng bánh xích rộng khi di chuyển trên nền đất mềm?",
      answer:
        "Bánh xích làm tăng diện tích tiếp xúc với mặt đất, giảm áp suất nên xe ít bị lún.",
      explanation: "Nêu được quan hệ giữa diện tích tiếp xúc và áp suất.",
    },
  ],
  9: [
    {
      type: "multiple_choice",
      level: "Nhận biết",
      prompt: "Đại lượng nào đặc trưng cho mức cản trở dòng điện của dây dẫn?",
      options: ["Điện trở", "Cường độ dòng điện", "Hiệu điện thế", "Công suất"],
      answer: "A. Điện trở",
      explanation: "Điện trở biểu thị mức độ cản trở dòng điện của dây dẫn.",
    },
    {
      type: "true_false",
      level: "Thông hiểu",
      prompt:
        "Với một dây dẫn có điện trở không đổi, cường độ dòng điện tỉ lệ thuận với hiệu điện thế hai đầu dây.",
      answer: "Đúng",
      explanation: "Theo định luật Ohm: I = U/R.",
    },
    {
      type: "short_answer",
      level: "Vận dụng",
      prompt:
        "Một điện trở 6 Ω được mắc vào hiệu điện thế 12 V. Tính cường độ dòng điện.",
      answer: "I = U/R = 12/6 = 2 A.",
      explanation: "Áp dụng định luật Ohm và ghi đúng đơn vị ampere.",
    },
    {
      type: "essay",
      level: "Vận dụng",
      prompt: "Giải thích vì sao cần ngắt nguồn điện trước khi thay bóng đèn.",
      answer:
        "Ngắt nguồn điện giúp dòng điện không chạy qua mạch, giảm nguy cơ điện giật và chập điện.",
      explanation:
        "Nêu được ít nhất một nguy cơ và cách ngắt nguồn giúp phòng tránh.",
    },
  ],
};

const alternativePrompts: Record<number, string[]> = {
  6: [
    "Để đo thể tích 50 mL nước trong phòng thực hành, em nên chọn dụng cụ nào?",
    "Ở áp suất tiêu chuẩn, nhiệt độ sôi của nước tinh khiết là 100 °C. Nhận định này đúng hay sai?",
    "Mô tả hai tính chất vật lí giúp em nhận biết khí oxygen.",
    "Một cốc nước lẫn cát cần được làm trong. Em chọn phương pháp tách nào? Giải thích lựa chọn của em.",
  ],
  7: [
    "Những loại hạt nào cấu tạo nên một nguyên tử?",
    "Một nguyên tử có số proton bằng số electron sẽ trung hoà về điện. Nhận định này đúng hay sai?",
    "Ánh sáng có vai trò gì trong quá trình quang hợp của cây xanh?",
    "Em cần làm gì để một chậu cây trong nhà sinh trưởng tốt? Nêu một cách làm và giải thích bằng kiến thức đã học.",
  ],
  8: [
    "Áp suất được biểu diễn bằng đơn vị nào trong hệ đơn vị quốc tế SI?",
    "Một vật chịu áp lực không đổi. Nếu diện tích bị ép nhỏ đi thì áp suất tăng. Nhận định này đúng hay sai?",
    "Một vật ép lên mặt sàn với lực 400 N trên diện tích 1 m². Áp suất tác dụng lên sàn bằng bao nhiêu?",
    "Bánh xích của xe tăng có diện tích tiếp xúc lớn. Đặc điểm này giúp xe đi trên đất mềm như thế nào?",
  ],
  9: [
    "Khả năng cản trở dòng điện của một dây dẫn được đặc trưng bằng đại lượng nào?",
    "Nếu điện trở giữ nguyên, tăng hiệu điện thế hai đầu dây dẫn làm tăng cường độ dòng điện. Nhận định này đúng hay sai?",
    "Mắc một điện trở 3 Ω vào hiệu điện thế 6 V. Tính cường độ dòng điện qua điện trở.",
    "Trước khi thay bóng đèn, người dùng ngắt nguồn điện. Hãy giải thích tác dụng của thao tác này.",
  ],
};

const learningObjectives: Record<number, string[]> = {
  6: [
    "Nhận biết dụng cụ đo thể tích chất lỏng.",
    "Mô tả nhiệt độ sôi của nước ở điều kiện áp suất tiêu chuẩn.",
    "Nêu được tính chất vật lí của oxygen.",
    "Lựa chọn và giải thích phương pháp tách một chất khỏi hỗn hợp.",
  ],
  7: [
    "Nhận biết các hạt cấu tạo nên nguyên tử.",
    "Giải thích vì sao nguyên tử trung hoà về điện.",
    "Nêu được vai trò của ánh sáng trong quang hợp.",
    "Vận dụng kiến thức sinh trưởng để đề xuất cách chăm sóc cây.",
  ],
  8: [
    "Nhận biết đơn vị áp suất trong hệ SI.",
    "Giải thích quan hệ giữa áp suất, áp lực và diện tích bị ép.",
    "Vận dụng công thức p = F/S để tính áp suất.",
    "Giải thích ứng dụng của việc tăng diện tích tiếp xúc trong đời sống.",
  ],
  9: [
    "Nhận biết ý nghĩa của điện trở.",
    "Mô tả quan hệ giữa cường độ dòng điện và hiệu điện thế khi điện trở không đổi.",
    "Vận dụng định luật Ohm để tính cường độ dòng điện.",
    "Giải thích một biện pháp bảo đảm an toàn điện.",
  ],
};

export function getLearningObjective(grade: number, index: number): string {
  return learningObjectives[grade][index];
}

export function getScoringGuide(grade: number, index: number): string {
  if (index === 0) return "Chọn đúng đáp án: 2,5 điểm; chọn sai: 0 điểm.";
  if (index === 1) return "Xác định đúng: 1 điểm; giải thích đúng: 1,5 điểm.";
  if (index === 2)
    return grade <= 7
      ? "Nêu đầy đủ nội dung trong đáp án gợi ý: 2,5 điểm; giáo viên phân bổ điểm cho câu trả lời một phần."
      : "Viết đúng công thức: 1 điểm; tính đúng kết quả: 1 điểm; ghi đúng đơn vị: 0,5 điểm.";
  return "Nêu đúng cách làm hoặc đặc điểm: 1 điểm; giải thích hợp lí bằng kiến thức đã học: 1,5 điểm.";
}

export function regenerateQuestion(
  grade: number,
  index: number,
  question: DemoQuestion,
): DemoQuestion {
  const revision = question.revision + 1;
  return {
    ...question,
    prompt:
      revision % 2 === 1
        ? alternativePrompts[grade][index]
        : samples[grade][index].prompt,
    // These alternate scenarios have the same answer; use the matching calculation explanation.
    answer:
      question.type === "short_answer" && grade === 8
        ? revision % 2 === 1
          ? "p = F/S = 400/1 = 400 Pa."
          : samples[grade][index].answer
        : question.type === "short_answer" && grade === 9
          ? revision % 2 === 1
            ? "I = U/R = 6/3 = 2 A."
            : samples[grade][index].answer
          : question.answer,
    approved: false,
    revision,
  };
}

export function isDemoExam(value: unknown): value is DemoExam {
  if (!value || typeof value !== "object") return false;
  const exam = value as DemoExam;
  return (
    typeof exam.id === "string" &&
    typeof exam.title === "string" &&
    [6, 7, 8, 9].includes(exam.grade) &&
    typeof exam.term === "string" &&
    Number.isFinite(exam.duration) &&
    exam.duration > 0 &&
    typeof exam.topic === "string" &&
    typeof exam.createdAt === "string" &&
    Array.isArray(exam.questions) &&
    exam.questions.length === 4 &&
    exam.questions.every(
      (question, index) =>
        question &&
        question.id === `q-${index + 1}` &&
        question.type === samples[exam.grade][index].type &&
        ["Nhận biết", "Thông hiểu", "Vận dụng"].includes(question.level) &&
        typeof question.prompt === "string" &&
        typeof question.answer === "string" &&
        typeof question.explanation === "string" &&
        typeof question.approved === "boolean" &&
        Number.isInteger(question.revision) &&
        question.revision >= 0 &&
        (question.options === undefined ||
          (Array.isArray(question.options) &&
            question.options.every((option) => typeof option === "string"))),
    )
  );
}

export function makeExam(
  input: Pick<DemoExam, "grade" | "term" | "duration" | "topic">,
): DemoExam {
  const grade = samples[input.grade] ? input.grade : 8;
  return {
    ...input,
    grade,
    id: `demo-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
    title: `Đề kiểm tra ${input.term} · KHTN ${grade}`,
    createdAt: new Date().toISOString(),
    questions: samples[grade].map((question, index) => ({
      ...question,
      id: `q-${index + 1}`,
      approved: false,
      revision: 0,
    })),
  };
}

export const sampleTopics: Record<number, string> = {
  6: "Đo lường, oxygen và tách chất khỏi hỗn hợp",
  7: "Nguyên tử và sinh trưởng ở thực vật",
  8: "Áp suất và ứng dụng trong đời sống",
  9: "Điện trở, định luật Ohm và an toàn điện",
};

export const seedExam: DemoExam = {
  ...makeExam({
    grade: 8,
    term: "Giữa kỳ I",
    duration: 45,
    topic: "Áp suất và ứng dụng trong đời sống",
  }),
  id: "de-minh-hoa-khtn-8",
  createdAt: "2026-09-15T08:00:00.000Z",
};

export const sampleDocuments = [
  {
    name: "Kế hoạch dạy học KHTN 8",
    kind: "PDF",
    note: "Tài liệu minh hoạ · 24 trang",
  },
  { name: "Chủ đề Áp suất", kind: "DOCX", note: "Tài liệu minh hoạ · 8 trang" },
  {
    name: "Ma trận kiểm tra giữa kỳ",
    kind: "XLSX",
    note: "Tài liệu minh hoạ · 2 trang",
  },
];
