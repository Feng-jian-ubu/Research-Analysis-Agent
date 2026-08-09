import { Link } from "react-router-dom";

function Header() {
  return (
    <header className="app-header">
      <div className="header-container">
        <Link className="brand" to="/">
          <span className="brand-icon">RA</span>

          <div className="brand-text">
            <span className="brand-title">Research Analysis Agent</span>
            <span className="brand-subtitle">智能数据分析助手</span>
          </div>
        </Link>

        <span className="header-badge">AI Agent</span>
      </div>
    </header>
  );
}

export default Header;