def load(stream):
    obj = {}
    
    # kernel: MCDDbSpecialDataElementImpl::load reads the text ID and the content, MCDDbSpecialDataImpl::load the semantic information
    obj['text_id'] = stream.loadNativeAsciiString()
    obj['content'] = stream.loadNativeAsciiString()
    obj['semantic_information'] = stream.loadNativeAsciiString()
    
    return obj
