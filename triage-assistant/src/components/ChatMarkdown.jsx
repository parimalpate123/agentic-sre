/**
 * Renders assistant / incident markdown safely (no raw HTML from user in this path).
 */
import ReactMarkdown from 'react-markdown';

const components = {
  h2: (props) => <h2 className="text-base font-semibold text-gray-900 mt-3 mb-2 first:mt-0" {...props} />,
  h3: (props) => <h3 className="text-sm font-semibold text-gray-800 mt-2 mb-1.5" {...props} />,
  p: (props) => <p className="mb-2 last:mb-0 text-gray-700 leading-relaxed" {...props} />,
  ul: (props) => <ul className="list-disc pl-5 mb-2 space-y-0.5" {...props} />,
  ol: (props) => <ol className="list-decimal pl-5 mb-2 space-y-0.5" {...props} />,
  li: (props) => <li className="text-gray-700 pl-0.5" {...props} />,
  strong: (props) => <strong className="font-semibold text-gray-900" {...props} />,
  a: ({ node, ...props }) => (
    <a className="text-violet-600 underline hover:text-violet-800" target="_blank" rel="noopener noreferrer" {...props} />
  ),
  blockquote: (props) => (
    <blockquote className="border-l-4 border-violet-200 pl-3 my-2 text-gray-600 italic" {...props} />
  ),
  code: ({ inline, className, children, ...props }) =>
    inline ? (
      <code className="bg-violet-50 text-violet-900 px-1 py-0.5 rounded text-[0.8em]" {...props}>
        {children}
      </code>
    ) : (
      <code
        className={`block bg-gray-900 text-gray-100 p-3 rounded-lg text-xs overflow-x-auto my-2 font-mono ${className || ''}`}
        {...props}
      >
        {children}
      </code>
    ),
  hr: () => <hr className="my-3 border-gray-200" />,
};

export default function ChatMarkdown({ children, className = '' }) {
  if (!children || !String(children).trim()) return null;
  return (
    <div className={`text-sm max-w-none chat-markdown ${className}`}>
      <ReactMarkdown components={components}>{String(children)}</ReactMarkdown>
    </div>
  );
}
