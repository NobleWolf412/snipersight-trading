import { useMemo } from 'react';

interface MarkdownViewerProps {
    content: string;
}

export function MarkdownViewer({ content }: MarkdownViewerProps) {
    const html = useMemo(() => {
        let processed = content
            .replace(/```([\s\S]*?)```/g, '<pre><code>$1</code></pre>')
            .replace(/`([^`]+)`/g, '<code>$1</code>')
            .replace(/^### (.*$)/gim, '<h3>$1</h3>')
            .replace(/^## (.*$)/gim, '<h2>$1</h2>')
            .replace(/^# (.*$)/gim, '<h1>$1</h1>')
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            .replace(/^\* (.*$)/gim, '<li>$1</li>')
            .replace(/^- (.*$)/gim, '<li>$1</li>')
            .replace(/^\d+\. (.*$)/gim, '<li>$1</li>')
            .replace(/\n\n/g, '</p><p>')
            .replace(/^(?!<[hl]|<pre|<li)(.*$)/gim, '<p>$1</p>')

        processed = processed.replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>')
        
        processed = processed
            .replace(/<p><\/p>/g, '')
            .replace(/<p>(<h[1-3]>)/g, '$1')
            .replace(/(<\/h[1-3]>)<\/p>/g, '$1')
            .replace(/<p>(<pre>)/g, '$1')
            .replace(/(<\/pre>)<\/p>/g, '$1')
            .replace(/<p>(<ul>)/g, '$1')
            .replace(/(<\/ul>)<\/p>/g, '$1')
        
        return processed
    }, [content])

    return (
        <div 
            className="prose max-w-none"
            dangerouslySetInnerHTML={{ __html: html }}
        />
    )
}