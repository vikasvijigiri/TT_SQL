    if (isPrepping) return;
    setIsPrepping(true);
    setPrepStatus('Starting');

    try {
      const response = await fetch(`${API_BASE_URL}/api/prep/run?force=${force}`, {
        method: 'POST'
      });
      if (!response.ok) throw new Error("Failed to start preparation");

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
            try {
              const data = JSON.parse(line.replace('data: ', '').trim());
              setPrepStatus(data.message);
              if (data.level === 'SUCCESS') {
                checkDbStatus();
                setTimeout(() => setPrepStatus('Ready'), 5000);
              } else if (data.level === 'ERROR') {
                setTimeout(() => setPrepStatus('Ready'), 5000);
              }
            } catch (e) {
              console.error("Error parsing SSE data", e);
            }
          }
        }
      }
    } catch (err) {
      console.error(err);
      setPrepStatus('Error');
      setTimeout(() => setPrepStatus('Ready'), 5000);
    } finally {
      setIsPrepping(false);
    }
  };

