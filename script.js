
const members = [
  {
    name: "Đặng Hoàng Phong",
    role: "Frontend Developer",
    image: "images/phong.jpg",
    intro: "Mình yêu thích xây dựng giao diện web hiện đại, dễ sử dụng và có tính thẩm mỹ.",
    skills: ["HTML", "CSS", "JavaScript", "Responsive Design"],
    projects: [
      "Website giới thiệu cá nhân",
      "Giao diện website bán hàng"
    ],
    email: "phong@example.com",
    github: "https://github.com/"
  },
  {
    name: "Lý Thế Vinh",
    role: "Backend Developer",
    image: "images/vinh.jpg",
    intro: "Mình quan tâm đến xử lý dữ liệu, thiết kế cơ sở dữ liệu và xây dựng API.",
    skills: ["C++", "Python", "SQL", "Database"],
    projects: [
      "Ứng dụng quản lý dữ liệu",
      "Hệ thống đăng nhập người dùng"
    ],
    email: "vinh@example.com",
    github: "https://github.com/"
  },
  {
    name: "Nguyễn Hoàng Phú",
    role: "Backend Developer",
    image: "./image/hoangphu.jpg",
    intro: "Mình là sinh viên Công nghệ thông tin, yêu thích lập trình và phát triển website.",
    skills: ["HTML", "CSS", "JavaScript", "C++", "Python", "SQL"],
    projects: [
      "Website portfolio cá nhân",
      "Ứng dụng quản lý sinh viên"
    ],
    email: "hoangphu31206@gmail.com",
    github: "https://github.com/phu031"
  },
  {
    name: "Nguyễn Võ Phương Uyên",
    role: "UI/UX Designer",
    image: "images/uyen.jpg",
    intro: "Mình yêu thích thiết kế giao diện trực quan, sáng tạo và mang lại trải nghiệm tốt.",
    skills: ["Figma", "UI Design", "UX Research", "HTML", "CSS"],
    projects: [
      "Thiết kế giao diện ứng dụng",
      "Thiết kế website giới thiệu"
    ],
    email: "uyen@example.com",
    github: "https://github.com/"
  }
];

// Năm hiện tại ở footer
document.getElementById("year").textContent = new Date().getFullYear();

// Hiệu ứng nghiêng 3D theo chuột
const cards = document.querySelectorAll(".member-card");

cards.forEach((card) => {
  card.addEventListener("mousemove", (event) => {
    const rect = card.getBoundingClientRect();

    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;

    const centerX = rect.width / 2;
    const centerY = rect.height / 2;

    const rotateX = ((y - centerY) / centerY) * -7;
    const rotateY = ((x - centerX) / centerX) * 7;

    card.style.transform =
      `perspective(1000px) rotateX(${rotateX}deg) rotateY(${rotateY}deg) translateY(-5px)`;
  });

  card.addEventListener("mouseleave", () => {
    card.style.transform =
      "perspective(1000px) rotateX(0deg) rotateY(0deg) translateY(0)";
  });
});

// Mở portfolio thành viên
const modal = document.getElementById("portfolioModal");
const modalBody = document.getElementById("modalBody");
const closeModal = document.getElementById("closeModal");

document.querySelectorAll(".member-card").forEach((card) => {
  card.querySelector(".view-btn").addEventListener("click", () => {
    const memberIndex = Number(card.dataset.member);
    const member = members[memberIndex];

    modalBody.innerHTML = `
      <img class="modal-avatar"
           src="${member.image}"
           alt="Ảnh ${member.name}"
           onerror="this.src='https://i.pravatar.cc/300?img=12'">

      <h2>${member.name}</h2>
      <span class="role">${member.role}</span>

      <h3>Giới thiệu</h3>
      <p>${member.intro}</p>

      <h3>Kỹ năng</h3>
      <ul>
        ${member.skills.map(skill => `<li>${skill}</li>`).join("")}
      </ul>

      <h3>Dự án tiêu biểu</h3>
      <ul>
        ${member.projects.map(project => `<li>${project}</li>`).join("")}
      </ul>

      <h3>Liên hệ</h3>
      <p>Email: <a href="mailto:${member.email}">${member.email}</a></p>
      <p>GitHub: <a href="${member.github}" target="_blank" rel="noopener noreferrer">Xem GitHub</a></p>
    `;

    modal.classList.add("show");
    document.body.style.overflow = "hidden";
  });
});

// Đóng modal
function hideModal() {
  modal.classList.remove("show");
  document.body.style.overflow = "";
}

closeModal.addEventListener("click", hideModal);

modal.addEventListener("click", (event) => {
  if (event.target === modal) {
    hideModal();
  }
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    hideModal();
  }
});

// Chuyển giao diện sáng/tối
const themeBtn = document.getElementById("themeBtn");

themeBtn.addEventListener("click", () => {
  document.body.classList.toggle("light");

  if (document.body.classList.contains("light")) {
    themeBtn.textContent = "☾";
  } else {
    themeBtn.textContent = "☀";
  }
});
