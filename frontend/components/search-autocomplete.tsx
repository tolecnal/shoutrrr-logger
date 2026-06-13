import React, { useState, useRef, useEffect, KeyboardEvent } from "react";
import { Input } from "@/components/ui/input";
import { Search } from "lucide-react";
import type { NotificationSearchFilters } from "@/lib/types";
import { useTranslations } from "next-intl";
import { validateQuery, highlightQueryHtml } from "@/lib/search-parser";
import { AlertCircle } from "lucide-react";

interface SearchAutocompleteProps {
  value: string;
  onChange: (val: string) => void;
  filters?: NotificationSearchFilters;
  inputRef?: React.RefObject<HTMLInputElement | null>;
}

const KEYS = ["title:", "message:", "sender:", "severity:", "tag:", "after:", "before:"];

export function SearchAutocomplete({ value, onChange, filters, inputRef }: SearchAutocompleteProps) {
  const t = useTranslations("SearchAutocomplete");
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [cursorPosition, setCursorPosition] = useState(0);
  const internalInputRef = useRef<HTMLInputElement>(null);
  const activeInputRef = inputRef || internalInputRef;
  const containerRef = useRef<HTMLDivElement>(null);
  
  const parseError = validateQuery(value);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setShowSuggestions(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const updateCursor = () => {
    if (activeInputRef.current) {
      setCursorPosition(activeInputRef.current.selectionStart || value.length);
    }
  };

  const getActiveWordInfo = () => {
    const cursor = cursorPosition;
    let start = cursor;
    while (start > 0 && value[start - 1] !== " ") start--;
    let end = cursor;
    while (end < value.length && value[end] !== " ") end++;
    return { word: value.slice(start, end), start, end };
  };

  const getSuggestions = () => {
    const { word } = getActiveWordInfo();
    if (!word) return []; // do not show keys by default when empty word to prevent intercepting Enter key

    const colonIndex = word.indexOf(":");
    if (colonIndex === -1) {
      // Suggest keys
      return KEYS.filter(k => k.startsWith(word.toLowerCase()));
    }

    // After colon
    const key = word.slice(0, colonIndex + 1).toLowerCase();
    const prefix = word.slice(colonIndex + 1).toLowerCase();

    if (key === "severity:") {
      const sevs = filters?.severities || ["info", "warning", "error", "critical"];
      return sevs.filter(s => s.startsWith(prefix)).map(s => key + s);
    }
    if (key === "sender:") {
      return (filters?.senders || []).filter(s => s.toLowerCase().startsWith(prefix)).map(s => key + s);
    }
    if (key === "tag:") {
      return (filters?.tags || []).filter(s => s.toLowerCase().startsWith(prefix)).map(s => key + s);
    }

    return [];
  };

  const suggestions = getSuggestions();

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (!showSuggestions || suggestions.length === 0) return;

    if (e.key === "ArrowDown") {
      e.preventDefault();
      setSelectedIndex((prev) => (prev + 1) % suggestions.length);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setSelectedIndex((prev) => (prev - 1 + suggestions.length) % suggestions.length);
    } else if (e.key === "Enter" || e.key === "Tab") {
      const { word } = getActiveWordInfo();
      if (word === suggestions[selectedIndex] && e.key === "Enter") {
        setShowSuggestions(false);
        return; // Allow form submission to proceed natively
      }
      e.preventDefault();
      applySuggestion(suggestions[selectedIndex]);
    } else if (e.key === "Escape") {
      setShowSuggestions(false);
    }
  };

  const applySuggestion = (suggestion: string) => {
    const { start, end } = getActiveWordInfo();
    const before = value.slice(0, start);
    const after = value.slice(end);
    
    const newValue = before + suggestion + (suggestion.endsWith(":") ? "" : " ") + after;
    onChange(newValue);
    setShowSuggestions(false);
    activeInputRef.current?.focus();
    
    // Set cursor position after the applied suggestion
    const newCursor = start + suggestion.length + (suggestion.endsWith(":") ? 0 : 1);
    setTimeout(() => {
      activeInputRef.current?.setSelectionRange(newCursor, newCursor);
    }, 0);
  };

  useEffect(() => {
    setSelectedIndex(0);
  }, [value]);

  return (
    <div className="relative flex-1" ref={containerRef}>
      <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground z-10" />
      
      <div className="relative w-full h-8 flex items-center bg-input border border-input rounded-md ring-offset-background focus-within:outline-none focus-within:ring-2 focus-within:ring-ring focus-within:ring-offset-2">
        {/* Highlight Layer */}
        <div 
          className="absolute inset-0 w-full h-full px-8 flex items-center text-sm font-mono whitespace-pre overflow-hidden pointer-events-none text-transparent"
          aria-hidden="true"
        >
          {/* We insert a zero-width space if value is empty so the div holds height properly, though absolute positioning handles that. */}
          <span dangerouslySetInnerHTML={{ __html: highlightQueryHtml(value) }} />
        </div>
        
        <input
          ref={activeInputRef}
          id="notification-search"
          name="notification-search"
          value={value}
          onChange={(e) => {
            onChange(e.target.value);
            setShowSuggestions(true);
            updateCursor();
          }}
          onClick={updateCursor}
          onKeyUp={updateCursor}
          onFocus={() => {
            setShowSuggestions(true);
            updateCursor();
          }}
          onKeyDown={handleKeyDown}
          placeholder={t('searchPlaceholder')}
          className="absolute inset-0 w-full h-full px-8 bg-transparent text-transparent caret-foreground outline-none text-sm font-mono focus:text-transparent selection:bg-primary/30 selection:text-transparent"
          autoComplete="off"
          spellCheck={false}
        />
        
        {parseError && value.trim().length > 0 && (
          <div className="absolute right-2 top-1/2 -translate-y-1/2" title={parseError.message}>
            <AlertCircle className="h-4 w-4 text-destructive" />
          </div>
        )}
      </div>

      {showSuggestions && suggestions.length > 0 && !parseError && (
        <div className="absolute z-50 w-full mt-1 bg-popover text-popover-foreground rounded-md border border-border shadow-md max-h-60 overflow-auto">
          {suggestions.map((s, i) => (
            <div
              key={s}
              className={`px-3 py-1.5 text-sm cursor-pointer hover:bg-accent hover:text-accent-foreground ${i === selectedIndex ? "bg-accent text-accent-foreground" : ""}`}
              onMouseDown={(e) => {
                e.preventDefault(); // keep input focused
                applySuggestion(s);
              }}
            >
              {s}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
