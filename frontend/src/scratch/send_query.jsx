
    const assistantMessageId = Date.now() + 1;
    setMessages(prev => [...prev, {
      id: assistantMessageId,
      role: 'assistant',
      content: '',
      status: 'Connecting...',
      type: 'thinking',
      payload: { business_summary: '', sql: '', results: [], columns: [], logs: [] }
    }]);

    setLoading(true);
    setCurrentStage('Initializing');

    try {
      const response = await fetch(`${API_BASE_URL}/api/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: query,
          db_name: '',
          dataset_name: selectedDataset,
          use_rag: true
        }),
      });

      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop();

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const jsonStr = line.replace('data: ', '').trim();
            if (!jsonStr) continue;

            try {
              const data = JSON.parse(jsonStr);

              if (data.type === 'section') {
                const stage = data.message.replace('\u{1F4A0}', '').trim();
                setCurrentStage(stage);
                setMessages(prev => {
                  const newMessages = [...prev];
                  const idx = newMessages.findIndex(m => m.id === assistantMessageId);
                  if (idx !== -1) {
                    newMessages[idx] = {
                      ...newMessages[idx],
                      status: stage,
                      payload: {
                        ...newMessages[idx].payload,
                        logs: [...(newMessages[idx].payload?.logs || []), stage]
                      }
                    };
                  }
                  return newMessages;
                });
              } else if (data.type === 'id') {
                setLastInstanceId(data.instance_id);
                setMessages(prev => {
                  const newMessages = [...prev];
                  const idx = newMessages.findIndex(m => m.id === assistantMessageId);
                  if (idx !== -1) {
                    newMessages[idx] = {
                      ...newMessages[idx],
                      instance_id: data.instance_id,
                      status: 'Initializing',
                      payload: { ...newMessages[idx].payload, instance_id: data.instance_id }
                    };
                  }
                  return newMessages;
                });
              } else if (data.type === 'token') {
                setMessages(prev => {
                  const newMessages = [...prev];
                  const idx = newMessages.findIndex(m => m.id === assistantMessageId);
                  if (idx !== -1) {
                    newMessages[idx] = {
                      ...newMessages[idx],
                      type: 'result',
                      status: 'Streaming Insights...',
                      payload: {
                        ...newMessages[idx].payload,
                        business_summary: (newMessages[idx].payload?.business_summary || '') + data.token
                      }
                    };
                  }
                  return newMessages;
                });
              } else if (data.type === 'result') {
                setMessages(prev => {
                  const newMessages = [...prev];
                  const idx = newMessages.findIndex(m => m.id === assistantMessageId);
                  if (idx !== -1) {
                    newMessages[idx] = {
                      ...newMessages[idx],
                      type: 'result',
                      status: null,
                      payload: {
                        sql: data.sql,
                        results: data.results || [],
                        columns: data.columns || [],
                        total_count: data.total_count || 0,
                        business_summary: data.business_summary,
                        chart_config: data.chart_config || null,
                        total_time: data.total_time
                      }
                    };
                  }
                  return newMessages;
                });
                setLoading(false);
                setCurrentStage('');
              } else if (data.type === 'error') {
                setMessages(prev => {
                  const newMessages = [...prev];
                  const idx = newMessages.findIndex(m => m.id === assistantMessageId);
                  if (idx !== -1) {
                    newMessages[idx] = {
                      ...newMessages[idx],
                      type: 'error',
                      content: data.message,
                      status: null
                    };
                  }
                  return newMessages;
                });
                setLoading(false);
                setCurrentStage('');
              }
            } catch (e) {
              console.error("Error parsing stream chunk:", e);
            }
          }
        }
      }
    } catch (err) {
      console.error(err);
      setMessages(prev => prev.map(m =>
        m.id === assistantMessageId ? { ...m, type: 'error', content: err.message, status: null } : m
      ));
      setLoading(false);
      setCurrentStage('');
    }
  };

  const navItems = [
    { id: 'projects', icon: FolderKanban, label: 'Projects' },
    { id: 'chat', icon: MessageSquare, label: 'Ask Data' },
    { id: 'database', icon: Database, label: 'Data Explorer' },
    { id: 'maintenance', icon: HardDrive, label: 'Storage' },
  ];

  return (
